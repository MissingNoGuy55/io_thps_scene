#include "main.h"

static const char* pszHelpInfo = "**************DXT COMPRESSOR FOR THUG PRO**************\nWritten by Stephen \"Missi\" Schmiedeberg\n----------------------------------------\n\nUSAGE:\ndxtcompressor [input file] [width] [height] [DXT1 or DXT5] [output file]\n----------------------------------------\n\nALL parameters are required\nThe input file must be ONLY pixels, with no headers or extra data present.\nDo note that this outputs raw pixel data to be read by THUG Pro, with no DDS header or anything that can be opened in an image editor.";

static int32_t flength;
static uint8_t* pBuf;
static uint8_t* pOut;
static uint8_t* pCached;

static char** s_iArgV;
static int s_iArgC;

#define GLX_CONTEXT_MAJOR_VERSION_ARB       0x2091
#define GLX_CONTEXT_MINOR_VERSION_ARB       0x2092

#ifdef __linux__
    typedef GLXContext (*glXCreateContextAttribsARBProc)(Display*, GLXFBConfig, GLXContext, Bool, const int*);
#endif

#ifdef _WIN32

PFNWGLCREATECONTEXTATTRIBSARBPROC wglCreateContextAttribsARB;
PFNGLGETCOMPRESSEDTEXIMAGEPROC glGetCompressedTexImage;

static HGLRC pHGLRC;

static HGLRC CreateGLContext(HDC pDC)
{
	PIXELFORMATDESCRIPTOR pfd;
	memset(&pfd, 0, sizeof(PIXELFORMATDESCRIPTOR));
	pfd.nSize  = sizeof(PIXELFORMATDESCRIPTOR);
	pfd.nVersion   = 1;
	pfd.dwFlags    = PFD_DOUBLEBUFFER | PFD_SUPPORT_OPENGL | PFD_DRAW_TO_WINDOW;
	pfd.iPixelType = PFD_TYPE_RGBA;
	pfd.cColorBits = 32;
	pfd.cDepthBits = 32;
	pfd.iLayerType = PFD_MAIN_PLANE;
	
	int nPixelFormat = ChoosePixelFormat(pDC, &pfd);
	
	if (nPixelFormat == 0) return FALSE;
	
	BOOL bResult = SetPixelFormat (pDC, nPixelFormat, &pfd);
	
	if (!bResult) return FALSE; 
	
	HGLRC tempContext = wglCreateContext(pDC);
	wglMakeCurrent(pDC, tempContext);
	
	int attribs[] =
	{
		WGL_CONTEXT_MAJOR_VERSION_ARB, 3,
		WGL_CONTEXT_MINOR_VERSION_ARB, 1,
		WGL_CONTEXT_FLAGS_ARB, 0,
		0
	};
	
    if( ( wglCreateContextAttribsARB = (PFNWGLCREATECONTEXTATTRIBSARBPROC)wglGetProcAddress("WGL_ARB_create_context") ) != NULL )
    {
		pHGLRC = wglCreateContextAttribsARB(pDC, 0, attribs);
		wglMakeCurrent(NULL,NULL);
		wglDeleteContext(tempContext);
		wglMakeCurrent(pDC, pHGLRC);
	}
	else
	{	//It's not possible to make a GL 3.x context. Use the old style context (GL 2.1 and before)
		pHGLRC = tempContext;
	}

	if( ( glGetCompressedTexImage = (PFNGLGETCOMPRESSEDTEXIMAGEPROC)wglGetProcAddress("glGetCompressedTexImage" ) ) != NULL )
    {
		printf( "Found glGetCompressedTexImage\n" );
	}

	//Checking GL version
	const GLubyte *GLVersionString = glGetString(GL_VERSION);

	//Or better yet, use the GL3 way to get the version number
	int OpenGLVersion[2];
	glGetIntegerv(GL_MAJOR_VERSION, &OpenGLVersion[0]);
	glGetIntegerv(GL_MINOR_VERSION, &OpenGLVersion[1]);

	if (!pHGLRC) return NULL;
	
	return pHGLRC;
}

LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam)
{
    switch(msg)
    {
        case WM_CLOSE:
            DestroyWindow(hwnd);
        break;
        case WM_DESTROY:
            PostQuitMessage(0);
        break;
        default:
            return DefWindowProc(hwnd, msg, wParam, lParam);
    }
    return 0;
}
#endif

int FindArgV( const char* pszArg )
{
    char** pszWork = NULL;
	int pos;

    for ( pszWork = s_iArgV, pos = 0; pszWork; pszWork++, pos++ )
	{
		if ( !strcmp( *pszWork, pszArg ) )
			return pos;
	}

    return -1;
}

static void ShowHelp()
{
    printf( "%s\n", pszHelpInfo );
}

static int image_memcmp( const void* mem1, const void* mem2, size_t count )
{
    if ( !mem1 || !mem2 )
        return 1;

    uint8_t* mem1_bytes = (uint8_t*)mem1;
    uint8_t* mem2_bytes = (uint8_t*)mem2;
    uint32_t c = 0;

    while (mem1_bytes)
    {
        if ( c > count )
            break;

        if (*mem1_bytes != *mem2_bytes )
            return 1;

        *mem1_bytes++;
        *mem2_bytes++;
        c++;
    }

    return 0;
}

int main( int argc, char** argv )
{
    FILE* f = NULL;
    int32_t width, height;
    GLint out_width = 0, out_height = 0, compressed_size = 0;
    GLuint compression = GL_RGBA;
    GLuint tex;
	int32_t cachedSize;
	
	s_iArgV = argv;
	s_iArgC = argc;

#ifdef _WIN32
    HGLRC pGLRC;
    HDC pDC;
    HWND pWindow;
#endif

    if ( s_iArgC < 5 )
    {
        ShowHelp();
        return 1;
    }
    else
    {
        f = fopen( argv[1], "rb" );

        if ( !f )
        {
            printf( "Could not open file \"%s\"", argv[1] );
            return 1;
        }

        width = argv[2] ? atoi(argv[2]) : 0;
        height = argv[3] ? atoi(argv[3]) : 0;

        fseek( f, 0, SEEK_END );
        flength = ftell( f );
        rewind(f);

        if ( argv[4] )
        {
            switch( atoi(argv[4]) )
            {
                case 0:
                    compression = GL_RGBA;
                    break;
                case 1:
                    compression = GL_COMPRESSED_RGBA_S3TC_DXT1_EXT;
                    break;
                case 5:
                    compression = GL_COMPRESSED_RGBA_S3TC_DXT5_EXT;
                    break;
                default:
                    printf("Unknown compression format");
                    return 1;
            }
        }

        pBuf = malloc( flength );

        memset( pBuf, 0, flength );

        fread( pBuf, sizeof( uint8_t ), flength, f );
        fclose( f );
        f = NULL;

        if ( !width || !height )
        {
            printf( "ERROR: No image width or height specified\n" );
            return 1;
        }
#ifdef __linux__
        int best_fbc = -1, worst_fbc = -1, best_num_samp = -1, worst_num_samp = 999;

        // Get a matching FB config
        static int visual_attribs[] =
        {
            GLX_X_RENDERABLE    , True,
            GLX_DRAWABLE_TYPE   , GLX_WINDOW_BIT,
            GLX_RENDER_TYPE     , GLX_RGBA_BIT,
            GLX_X_VISUAL_TYPE   , GLX_TRUE_COLOR,
            GLX_RED_SIZE        , 8,
            GLX_GREEN_SIZE      , 8,
            GLX_BLUE_SIZE       , 8,
            GLX_ALPHA_SIZE      , 8,
            GLX_DEPTH_SIZE      , 24,
            GLX_STENCIL_SIZE    , 8,
            GLX_DOUBLEBUFFER    , True,
            //GLX_SAMPLE_BUFFERS  , 1,
            //GLX_SAMPLES         , 4,
            None
        };

        Display *display = XOpenDisplay(NULL);
        int fbcount;
        GLXFBConfig* fbc = glXChooseFBConfig(display, DefaultScreen(display), visual_attribs, &fbcount);

        int i;
        for (i=0; i<fbcount; ++i)
        {
            XVisualInfo *vi = glXGetVisualFromFBConfig( display, fbc[i] );
            if ( vi )
            {
            int samp_buf, samples;
            glXGetFBConfigAttrib( display, fbc[i], GLX_SAMPLE_BUFFERS, &samp_buf );
            glXGetFBConfigAttrib( display, fbc[i], GLX_SAMPLES       , &samples  );

            printf( "  Matching fbconfig %d, visual ID 0x%2x: SAMPLE_BUFFERS = %d,"
                    " SAMPLES = %d\n",
                    i, vi -> visualid, samp_buf, samples );

            if ( ( best_fbc < 0 || samp_buf ) && samples > best_num_samp )
                best_fbc = i, best_num_samp = samples;
            if ( worst_fbc < 0 || !samp_buf || samples < worst_num_samp )
                worst_fbc = i, worst_num_samp = samples;
            }
            XFree( vi );
        }

        GLXFBConfig bestFbc = fbc[ best_fbc ];

        // Get a visual
        XVisualInfo *vi = glXGetVisualFromFBConfig( display, bestFbc );

        // Be sure to free the FBConfig list allocated by glXChooseFBConfig()
        XFree( fbc );

        glXCreateContextAttribsARBProc glXCreateContextAttribsARB = 0;
        glXCreateContextAttribsARB = (glXCreateContextAttribsARBProc)
                glXGetProcAddressARB( (const GLubyte *) "glXCreateContextAttribsARB" );

        XSetWindowAttributes swa;
        Colormap cmap;
        swa.colormap = cmap = XCreateColormap( display,
                                                RootWindow( display, vi->screen ),
                                                vi->visual, AllocNone );
        swa.background_pixmap = None ;
        swa.border_pixel      = 0;
        swa.event_mask        = StructureNotifyMask;

        Window win = XCreateWindow( display, RootWindow( display, vi->screen ),
                              0, 0, 100, 100, 0, vi->depth, InputOutput,
                              vi->visual,
                              CWBorderPixel|CWColormap|CWEventMask, &swa );

        int context_attribs[] =
        {
            GLX_CONTEXT_MAJOR_VERSION_ARB, 3,
            GLX_CONTEXT_MINOR_VERSION_ARB, 0,
            //GLX_CONTEXT_FLAGS_ARB        , GLX_CONTEXT_FORWARD_COMPATIBLE_BIT_ARB,
            None
        };
        GLXContext ctx = 0;
        ctx = glXCreateContextAttribsARB( display, bestFbc, 0,
                                      True, context_attribs );

        if ( glGetError() != GL_NO_ERROR )
            return 1;

        // Sync to ensure any errors generated are processed.
        XSync( display, False );

        if ( glGetError() != GL_NO_ERROR )
            return 1;

        XSync( display, False );

        if ( glGetError() != GL_NO_ERROR )
            return 1;

        glXMakeCurrent( display, win, ctx );

        if ( glGetError() != GL_NO_ERROR )
            return 1;
#elif _WIN32

        // Register the window class.
        const wchar_t CLASS_NAME[]  = L"Sample Window Class";

        WNDCLASS wc;

        memset( &wc, 0, sizeof( WNDCLASS ) );

        wc.lpfnWndProc   = WndProc;
        wc.hInstance     = GetModuleHandle(NULL);
        wc.lpszClassName = CLASS_NAME;

        RegisterClass(&wc);

        // Step 2: Creating the Window
        pWindow = CreateWindowEx(
        0,                              // Optional window styles.
        CLASS_NAME,                     // Window class
        L"Dummy",                       // Window text
        WS_OVERLAPPEDWINDOW,            // Window style

        // Size and position
        CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT,

        NULL,       // Parent window    
        NULL,       // Menu
        GetModuleHandle(NULL),       // Instance handle
        NULL        // Additional application data
        );

        if(pWindow == NULL)
        {
            MessageBox(NULL, L"Window Creation Failed!", L"Error!",
                MB_ICONEXCLAMATION | MB_OK);
            return 0;
        }

        pDC = GetDC( pWindow );

        pGLRC = CreateGLContext( pDC );
#endif

        glGenTextures( 1, &tex );

        if ( glGetError() != GL_NO_ERROR )
            return 1;

        glBindTexture( GL_TEXTURE_2D, tex );

        if ( glGetError() != GL_NO_ERROR )
            return 1;

        glTexImage2D( GL_TEXTURE_2D,
                    0,
                    compression,
                    width,  // level_img_width,
                    height,  // level_img_height,
                    0,
                    GL_RGBA,
                    GL_FLOAT,
                    pBuf );

        if ( glGetError() != GL_NO_ERROR )
            return 1;

        glGetTexLevelParameteriv( GL_TEXTURE_2D, 0, GL_TEXTURE_WIDTH, &out_width );

        if ( glGetError() != GL_NO_ERROR )
            return 1;

        glGetTexLevelParameteriv( GL_TEXTURE_2D, 0, GL_TEXTURE_HEIGHT, &out_height );

        if ( glGetError() != GL_NO_ERROR )
            return 1;

        glGetTexLevelParameteriv( GL_TEXTURE_2D, 0, GL_TEXTURE_COMPRESSED_IMAGE_SIZE, &compressed_size );

        if ( glGetError() != GL_NO_ERROR )
            return 1;

        pOut = malloc( compressed_size );
        memset( pOut, 0, compressed_size );

        glGetCompressedTexImage( GL_TEXTURE_2D, 0, pOut );
		
		// Check for a cached version
		if ( ( f = fopen( argv[5], "rb" ) ) != NULL )
		{
			fseek( f, 0, SEEK_END );
			cachedSize = ftell( f );
			rewind( f );

			pCached = malloc( cachedSize );
			memset( pCached, 0, cachedSize );

			fread( pCached, 1, cachedSize, f );
			fclose( f );
			f = NULL;

            if ( cachedSize == compressed_size && image_memcmp( pCached, pOut, cachedSize ) == 0 )
            {
                free( pCached );
                pCached = NULL;

                printf( "Input file matches the output file\n" );
                return 0;
            }

            free( pCached );
            pCached = NULL;
		}
		
        f = fopen( argv[5], "wb" );
        fwrite( pOut, 1, compressed_size, f );
        fclose( f );
        f = NULL;

        free( pBuf );
        pBuf = NULL;
        free( pOut );
        pOut = NULL;

        printf("Finished!\n");
    }

    return 0;
}
