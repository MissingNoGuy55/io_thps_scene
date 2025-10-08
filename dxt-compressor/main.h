#pragma once

#ifdef _WIN32
#define _CRT_SECURE_NO_WARNINGS
#endif

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stddef.h>
#include <string.h>
#include <math.h>

#ifdef __linux__
      #include <GL/gl.h>
      #include <sys/param.h>
      #include <GL/glext.h>
      #include <GL/glx.h>
      #include <GL/glxext.h>
      #include <GL/glu.h>
      #include <X11/Xlib.h>
      #include <X11/Xutil.h>
#endif

#if defined(__CYGWIN__) || defined( _WIN32 )
      #include <GL/gl.h>
      #include <GL/glu.h>
      #include <GL/glext.h>
      #include <GL/wgl.h>
      #include <GL/wglext.h>
      #include <windows.h>
#endif
