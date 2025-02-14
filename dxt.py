#----------------------------------------------------------------------------------
#- Missi: DXT compression and mipmap routines that have been borrowed and converted 
#- from the GIMP DDS plugin. Note that since BGL is deprecated and no longer 
#- accessible from Blender 3.5 onwards, the methods in this file must be used to
#- create DXT textures on level export.
#----------------------------------------------------------------------------------

import bpy
import os
import struct
import math
import numpy as np

#----------------------------------------------------------------------------------
#- Missi: Color methods
#----------------------------------------------------------------------------------

def swap_rb( pixels, n, bpp ):
    for i in range( 0, n ):
        t = pixels[bpp * i + 0]
        pixels[bpp * i + 0] = pixels[bpp * i + 2]
        pixels[bpp * i + 2] = t

def linear_to_sRGB( c ):
    v = float(c) / 255.0
   
    if v < 0:
        v = 0
    elif v > 1:
        v = 1
    elif v <= 0.0031308:
        v = 12.92 * v
    else:
        v = 1.055 * powf(v, 0.41666) - 0.055;
   
    return int(math.floor(255.0 * v + 0.5))

def sRGB_to_linear( c ):
    v = float(c) / 255.0;
   
    if v < 0:
        v = 0
    elif v > 1:
        v = 1
    elif v <= 0.04045:
        v /= 12.92
    else:
        v = powf((v + 0.055) / 1.055, 2.4)
   
    return int(math.floor(255.0 * v + 0.5))

def linear_to_gamma( gc, v, gamma ):

    if gc == 1:
        v = int(pow(float(v) / 255.0, gamma)) * 255
        if(v > 255): v = 255
    elif gc == 2:
        v = linear_to_sRGB(v)

    return v
    
def gamma_to_linear( gc, v, gamma ):
    if gc == 1:
        v = int( pow( float( v ) / 255.0, 1.0 / gamma ) ) * 255
        if v > 255 : v = 255
    elif gc == 2:
        v = sRGB_to_linear( v )
    
    return v

#----------------------------------------------------------------------------------
#- Missi: Mipmap filter methods
#----------------------------------------------------------------------------------

def box_filter( t ):
    if (t >= -0.5) and (t < 0.5):
        return 1.0

    return 0.0

def triangle_filter( t ):
    if t < 0.0: t = -t
    if t < 1.0: return ( 1.0 - t )
    
    return(0.0);

def quadratic_filter( t ):
    if t < 0.0: t = -t
    if t < 0.5: return ( 0.75 - t * t )
    if t < 1.5:
        t -= 1.5
        return ( 0.5 * t * t )
      
    return 0.0

def bspline_filter( t ):
    tt = 0.0

    if t < 0.0: t = -t
   
    if t < 1.0:
        tt = t * t
        return ( ( ( 0.5 * tt * t ) - tt + ( 2.0 / 3.0 ) ) )

    elif t < 2.0:
        t = 2.0 - t
        return ( ( 1.0 / 6.0 ) * ( t * t * t ) )

    return 0.0

def mitchell( t, B, C ):
    tt = 0.0

    tt = t * t;
    if t < 0.0: t = -t

    if t < 1.0:
        t = (((12.0 - 9.0 * B - 6.0 * C) * (t * tt)) + ((-18.0 + 12.0 * B + 6.0 * C) * tt) + (6.0 - 2.0 * B))
        return (t / 6.0)

    elif t < 2.0:
        t = (((-1.0 * B - 6.0 * C) * (t * tt)) + ((6.0 * B + 30.0 * C) * tt) + ((-12.0 * B - 48.0 * C) * t) + (8.0 * B + 24.0 * C))
        return ( t / 6.0 )

    return 0.0

def mitchell_filter( t ):
    return mitchell( t, 1.0 / 3.0, 1.0 / 3.0);

def sinc( x ):
    x = (x * math.pi)
    if abs(x) < 1e-04:
        return ( 1.0 + x * x * ( -1.0 / 6.0 + x * x * 1.0 / 120.0 ) )

    return ( math.sin(x) / x )

def lanczos_filter( t ):
    if t < 0.0: t = -t
    if t < 3.0: return ( sinc( t ) * sinc( t / 3.0 ) )
    return 0.0

def bessel0( x ):
    EPSILON = 1e-6
    xh = sum = pow = ds = 0.0

    xh = 0.5 * x
    sum = 1.0
    pow = 1.0
    k = 0
    ds = 1.0
    while ds > sum * EPSILON:
        k += 1
        pow = pow * (xh / k)
        ds = pow * pow
        sum += ds

    return sum

def kaiser_filter( t ):
    if t < 0.0: t = -t

    if t < 3.0:
        alpha = 4.0
        rb04 = 0.0884805322 # 1.0f / bessel0(4.0f);
        ratio = t / 3.0
        if ( 1.0 - ratio * ratio ) >= 0:
            return ( sinc( t ) * bessel0( alpha * sqrtf( 1.0 - ratio * ratio ) ) * rb04 )

    return 0.0

#----------------------------------------------------------------------------------
#- Missi: Block encoding functions 
#----------------------------------------------------------------------------------

def block_count( w, h ):
    return ((((h) + 3) >> 2) * (((w) + 3) >> 2))

def block_offset( x, y, w, bs ):
    return (((y) >> 2) * ((bs) * (((w) + 3) >> 2)) + ((bs) * ((x) >> 2)))

#----------------------------------------------------------------------------------
#- Missi: Mipmap methods, classes and variables 
#----------------------------------------------------------------------------------

DDS_MIPMAP_FILTER_DEFAULT = 0
DDS_MIPMAP_FILTER_NEAREST = 1
DDS_MIPMAP_FILTER_BOX = 2
DDS_MIPMAP_FILTER_TRIANGLE = 3
DDS_MIPMAP_FILTER_QUADRATIC = 4
DDS_MIPMAP_FILTER_BSPLINE = 5
DDS_MIPMAP_FILTER_MITCHELL = 6
DDS_MIPMAP_FILTER_LANCZOS = 7
DDS_MIPMAP_FILTER_KAISER = 8

DDS_MIPMAP_WRAP_DEFAULT = 0
DDS_MIPMAP_WRAP_MIRROR = 1
DDS_MIPMAP_WRAP_REPEAT = 2
DDS_MIPMAP_WRAP_CLAMP = 3

class mipfilter:
    def __init__ ( self, filter_name, filter_func, support ):
        self.filter = filter_name
        self.func = filter_func
        self.support = support
        
filters = [ mipfilter( DDS_MIPMAP_FILTER_BOX, box_filter, 0.5 ),
            mipfilter( DDS_MIPMAP_FILTER_TRIANGLE, triangle_filter, 1.0 ),
            mipfilter( DDS_MIPMAP_FILTER_QUADRATIC, quadratic_filter, 1.5 ),
            mipfilter( DDS_MIPMAP_FILTER_BSPLINE, bspline_filter, 2.0 ),
            mipfilter( DDS_MIPMAP_FILTER_MITCHELL, mitchell_filter, 2.0 ),
            mipfilter( DDS_MIPMAP_FILTER_LANCZOS, lanczos_filter, 3.0 ),
            mipfilter( DDS_MIPMAP_FILTER_KAISER, kaiser_filter, 3.0 ) ]

###############################################################################
## wrap modes                                                                 #
###############################################################################

def wrap_mirror(x, max):
    if max == 1: x = 0
    x = abs(x)
    while x >= max:
        x = abs(max + max - x - 2)
    return x

def wrap_repeat(x, max):
    if x >= 0: return (x % max)
    return ((x + 1) % max + max - 1);

def wrap_clamp(x, maxval):
    return(max(0, min(maxval - 1, x)));

###############################################################################

def calc_alpha_test_coverage( src, width, height, bpp, alpha_test_threshold, alpha_scale ):
    x = 0
    y = 0
    rowbytes = width * bpp
    coverage = 0
    alpha_channel_idx = 3

    if bpp <= alpha_channel_idx:
        return 1.0

    for y in range( 0, height ):
        for x in range( 0, width ):
            alpha = src[y * rowbytes + (x * bpp) + alpha_channel_idx]
            if (alpha * alpha_scale) >= (alpha_test_threshold * 255):
                coverage += 1;

    return float(coverage / (width * height))
    
def scale_alpha_to_coverage( img, width, height, bpp, desired_coverage, alpha_test_threshold ):
    x = y = 0
    rowbytes = width * bpp
    alpha_channel_idx = 3
    min_alpha_scale = 0.0
    max_alpha_scale = 4.0
    alpha_scale = 1.0

    if bpp <= alpha_channel_idx:
        # No alpha channel
        return;

    # Binary search
    for i in range( 0, 10 ):
        cur_coverage = calc_alpha_test_coverage( img, width, height, bpp, alpha_test_threshold, alpha_scale )

        if cur_coverage < desired_coverage:
            min_alpha_scale = alpha_scale
        elif cur_coverage > desired_coverage :
            max_alpha_scale = alpha_scale
        else:
            break

        alpha_scale = (min_alpha_scale + max_alpha_scale) / 2

    # Scale alpha channel
    for y in range( 0, height ):
        for x in range( 0, width ):
            new_alpha = img[y * rowbytes + (x * bpp) + alpha_channel_idx] * alpha_scale
            if(new_alpha > 255.0):
                new_alpha = 255.0

            img[y * rowbytes + (x * bpp) + alpha_channel_idx] = new_alpha

def scale_image_nearest( dst, dw, dh, src, sw, sh, bpp, filter, support, wrap, gc, gamma):
    n = x = y = 0
    ix = iy = 0
    srowbytes = sw * bpp
    drowbytes = dw * bpp

    for y in range( 0, dh ):
        iy = (y * sh + sh / 2) / dh
        for x in range( 0, dw ):
            ix = (x * sw + sw / 2) / dw
            for n in range( 0, bpp ):
                dst[y * drowbytes + (x * bpp) + n] = src[ int( iy * srowbytes + (ix * bpp) + n ) ]


def scale_image( dst, dw, dh, src, sw, sh, bpp, filter, support, wrap, gc, gamma ):
    blur = 1.0
    xfactor = float(dw) / float(sw)
    yfactor = float(dh) / float(sh)

    x = y = start = stop = nmax = 0
    sstride = sw * bpp;
    center = contrib = density = s = r = t = 0.0

    d = row = col = None

    xscale = min(xfactor, 1.0) / blur;
    yscale = min(yfactor, 1.0) / blur;
    xsupport = support / xscale;
    ysupport = support / yscale;

    if xsupport <= 0.5:
        xsupport = 0.5 + 1e-10
        xscale = 1.0

    if ysupport <= 0.5:
        ysupport = 0.5 + 1e-10
        yscale = 1.0

    tmp = np.empty(sw * bpp, dtype=np.ubyte) #bytearray( sw * bpp )

    for y in range( 0, dh ):
        # resample in Y direction to temp buffer
        d = tmp

        center = (float(y) + 0.5) / yfactor
        start = int(center - ysupport + 0.5)
        stop  = int(center + ysupport + 0.5)
        nmax = stop - start
        s = float(start) - center + 0.5

        for x in range( 0, sw ):
            col = src[(x * bpp):]

            for i in range( 0, bpp ):
                density = 0.0
                r = 0.0

                for n in range( 0, nmax ):
                    contrib = filter((s + n) * yscale)
                    density += contrib
                    if i == 3:
                        t = col[(wrap(start + n, sh) * sstride) + i]
                    else:
                        t = linear_to_gamma( gc, col[(wrap(start + n, sh) * sstride) + i], gamma )
                    r += t * contrib

                if density != 0.0 and density != 1.0:
                    r /= density

                r = min(255, max(0, r))

                if i != 3:
                   r = gamma_to_linear(gc, r, gamma)

                d[(x * bpp) + i] = int( r )

        # resample in X direction using temp buffer
        row = d;
        d = dst;

        for x in range( 0, dw ): #for(x = 0; x < dw; ++x)
            center = float(x + 0.5) / xfactor
            start = int(center - xsupport + 0.5)
            stop  = int(center + xsupport + 0.5)
            nmax = stop - start;
            s = float(start) - center + 0.5;

            for i in range( 0, bpp ):
                density = 0.0
                r = 0.0

                for n in range( 0, nmax ):
                    contrib = filter((s + n) * xscale)
                    density += contrib
                    if i == 3:
                        t = row[(wrap(start + n, sw) * bpp) + i]
                    else:
                        t = linear_to_gamma( gc, row[ ( wrap( start + n, sw ) * bpp ) + i ], gamma )
                    r += t * contrib

            if density != 0.0 and density != 1.0:
                r /= density

            r = min(255, max(0, r))

            if i != 3:
                r = gamma_to_linear(gc, r, gamma)

            d[(y * (dw * bpp)) + (x * bpp) + i] = int( r )

    del tmp

def generate_mipmaps( dst, src, width, height, bpp, indexed, mipmaps, filter, wrap, gc, gamma, preserve_alpha_coverage, alpha_test_threshold ):
    i = 0
    sw = 0
    sh = 0
    dw = 0
    dh = 0
    s = None
    d = np.empty( (width * height * bpp), dtype=np.ubyte )
    mipmap_func = None
    filter_func = None
    wrap_func = None
    support = 0.0
    has_alpha = (bpp >= 3)
    alpha_test_coverage = 1.0;

    if indexed or filter == DDS_MIPMAP_FILTER_NEAREST:
        mipmap_func = scale_image_nearest
    else:
        if filter <= DDS_MIPMAP_FILTER_DEFAULT or filter >= len(filters):
            filter = DDS_MIPMAP_FILTER_BOX

        mipmap_func = scale_image

        for i in range( 0, len(filters) ):
            if(filter == filters[i].filter):
                filter_func = filters[i].func
                support = filters[i].support

    match wrap:
        case 1:
            wrap_func = wrap_mirror
          
        case 2:
            wrap_func = wrap_repeat
          
        case 3:
            wrap_func = wrap_clamp
          
        case _:
            wrap_func = wrap_clamp

    if has_alpha and preserve_alpha_coverage:
        alpha_test_coverage = calc_alpha_test_coverage(src, width, height, bpp, alpha_test_threshold, 1.0);

    # memcpy(dst, src, width * height * bpp);
    
    for i in range( 0, len( src ) ):
        dst[i] = src[i]
        
    #dst[:] = src[:]

    s = dst
    d[:] = dst[:len(d)]

    sw = width
    sh = height

    for i in range( 1, mipmaps ):
        dw = max(1, sw >> 1);
        dh = max(1, sh >> 1);

        mipmap_func( d, dw, dh, s, sw, sh, bpp, filter_func, support, wrap_func, gc, gamma )

        if has_alpha and preserve_alpha_coverage:
            scale_alpha_to_coverage( d, dw, dh, bpp, alpha_test_coverage, alpha_test_threshold )

        s = d
        sw = dw
        sh = dh
        
        d = d[(dw * dh * bpp):]
    
#----------------------------------------------------------------------------------
#- Missi: Compression methods, classes and variables 
#----------------------------------------------------------------------------------

class vec4_t:
    
    """4D vector class"""
    def __init__(self, x=0.0, y=0.0, z=0.0, w=0.0):
        self.x = x
        self.y = y
        self.z = z
        self.w = w
        
    def __add__( self, other ):
        self.x += other.x
        self.y += other.y
        self.z += other.z
        self.w += other.w
        return self
        
    def __sub__( self, other ):
        self.x -= other.x
        self.y -= other.y
        self.z -= other.z
        self.w -= other.w
        return self
        
    def __mul__( self, other ):
        self.x *= other.x
        self.y *= other.y
        self.z *= other.z
        self.w *= other.w
        return self
        
    def __truediv__( self, other ):
        self.x /= other.x
        self.y /= other.y
        self.z /= other.z
        self.w /= other.w
        return self


DDS_COMPRESS_NONE = 0
DDS_COMPRESS_BC1 = 1        # DXT1
DDS_COMPRESS_BC2 = 2        # DXT3
DDS_COMPRESS_BC3 = 3        # DXT5
DDS_COMPRESS_BC3N = 4       # DXT5n
DDS_COMPRESS_BC4 = 5        # ATI1
DDS_COMPRESS_BC5 = 6        # ATI2
DDS_COMPRESS_RXGB = 7       # DXT5
DDS_COMPRESS_AEXP = 8       # DXT5
DDS_COMPRESS_YCOCG = 9      # DXT5
DDS_COMPRESS_YCOCGS = 10    # DXT5

DDS_FORMAT_DEFAULT = 0
DDS_FORMAT_RGB8 = 1
DDS_FORMAT_RGBA8 = 2
DDS_FORMAT_BGR8 = 3
DDS_FORMAT_ABGR8 = 4
DDS_FORMAT_R5G6B5 = 5
DDS_FORMAT_RGBA4 = 6
DDS_FORMAT_RGB5A1 = 7
DDS_FORMAT_RGB10A2 = 8
DDS_FORMAT_R3G3B2 = 9
DDS_FORMAT_A8 = 10
DDS_FORMAT_L8 = 11
DDS_FORMAT_L8A8 = 12
DDS_FORMAT_AEXP = 13
DDS_FORMAT_YCOCG = 14

DXT_BC1           = 1 << 0
DXT_BC2           = 1 << 1
DXT_BC3           = 1 << 2
DXT_PERCEPTUAL    = 1 << 3

V4HALF = vec4_t( 0.5, 0.5, 0.5, 0.5 )
V4GRID = vec4_t( 31.0, 63.0, 31.0, 0.0 )
V4GRIDRCP = vec4_t( 1.0 / 31.0, 1.0 / 63.0, 1.0 / 31.0 )
V4ZERO = vec4_t(0.0, 0.0, 0.0, 0.0)
V4ONE = vec4_t(1.0, 1.0, 1.0, 1.0)
V4ONETHIRD  = vec4_t(1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)
V4TWOTHIRDS = vec4_t(2.0 / 3.0, 2.0 / 3.0, 2.0 / 3.0)
V4EPSILON   = vec4_t(1e-04, 1e-04, 1e-04, 1e-04)

omatch5 = [ [0x00, 0x00], [0x00, 0x00], [0x00, 0x01], [0x00, 0x01], 
   [0x01, 0x00], [0x01, 0x00], [0x01, 0x00], [0x01, 0x01], 
   [0x01, 0x01], [0x01, 0x01], [0x01, 0x02], [0x00, 0x04], 
   [0x02, 0x01], [0x02, 0x01], [0x02, 0x01], [0x02, 0x02], 
   [0x02, 0x02], [0x02, 0x02], [0x02, 0x03], [0x01, 0x05], 
   [0x03, 0x02], [0x03, 0x02], [0x04, 0x00], [0x03, 0x03], 
   [0x03, 0x03], [0x03, 0x03], [0x03, 0x04], [0x03, 0x04], 
   [0x03, 0x04], [0x03, 0x05], [0x04, 0x03], [0x04, 0x03], 
   [0x05, 0x02], [0x04, 0x04], [0x04, 0x04], [0x04, 0x05], 
   [0x04, 0x05], [0x05, 0x04], [0x05, 0x04], [0x05, 0x04], 
   [0x06, 0x03], [0x05, 0x05], [0x05, 0x05], [0x05, 0x06], 
   [0x04, 0x08], [0x06, 0x05], [0x06, 0x05], [0x06, 0x05], 
   [0x06, 0x06], [0x06, 0x06], [0x06, 0x06], [0x06, 0x07], 
   [0x05, 0x09], [0x07, 0x06], [0x07, 0x06], [0x08, 0x04], 
   [0x07, 0x07], [0x07, 0x07], [0x07, 0x07], [0x07, 0x08], 
   [0x07, 0x08], [0x07, 0x08], [0x07, 0x09], [0x08, 0x07], 
   [0x08, 0x07], [0x09, 0x06], [0x08, 0x08], [0x08, 0x08], 
   [0x08, 0x09], [0x08, 0x09], [0x09, 0x08], [0x09, 0x08], 
   [0x09, 0x08], [0x0a, 0x07], [0x09, 0x09], [0x09, 0x09], 
   [0x09, 0x0a], [0x08, 0x0c], [0x0a, 0x09], [0x0a, 0x09], 
   [0x0a, 0x09], [0x0a, 0x0a], [0x0a, 0x0a], [0x0a, 0x0a], 
   [0x0a, 0x0b], [0x09, 0x0d], [0x0b, 0x0a], [0x0b, 0x0a], 
   [0x0c, 0x08], [0x0b, 0x0b], [0x0b, 0x0b], [0x0b, 0x0b], 
   [0x0b, 0x0c], [0x0b, 0x0c], [0x0b, 0x0c], [0x0b, 0x0d], 
   [0x0c, 0x0b], [0x0c, 0x0b], [0x0d, 0x0a], [0x0c, 0x0c], 
   [0x0c, 0x0c], [0x0c, 0x0d], [0x0c, 0x0d], [0x0d, 0x0c], 
   [0x0d, 0x0c], [0x0d, 0x0c], [0x0e, 0x0b], [0x0d, 0x0d], 
   [0x0d, 0x0d], [0x0d, 0x0e], [0x0c, 0x10], [0x0e, 0x0d], 
   [0x0e, 0x0d], [0x0e, 0x0d], [0x0e, 0x0e], [0x0e, 0x0e], 
   [0x0e, 0x0e], [0x0e, 0x0f], [0x0d, 0x11], [0x0f, 0x0e], 
   [0x0f, 0x0e], [0x10, 0x0c], [0x0f, 0x0f], [0x0f, 0x0f], 
   [0x0f, 0x0f], [0x0f, 0x10], [0x0f, 0x10], [0x0f, 0x10], 
   [0x0f, 0x11], [0x10, 0x0f], [0x10, 0x0f], [0x11, 0x0e], 
   [0x10, 0x10], [0x10, 0x10], [0x10, 0x11], [0x10, 0x11], 
   [0x11, 0x10], [0x11, 0x10], [0x11, 0x10], [0x12, 0x0f], 
   [0x11, 0x11], [0x11, 0x11], [0x11, 0x12], [0x10, 0x14], 
   [0x12, 0x11], [0x12, 0x11], [0x12, 0x11], [0x12, 0x12], 
   [0x12, 0x12], [0x12, 0x12], [0x12, 0x13], [0x11, 0x15], 
   [0x13, 0x12], [0x13, 0x12], [0x14, 0x10], [0x13, 0x13], 
   [0x13, 0x13], [0x13, 0x13], [0x13, 0x14], [0x13, 0x14], 
   [0x13, 0x14], [0x13, 0x15], [0x14, 0x13], [0x14, 0x13], 
   [0x15, 0x12], [0x14, 0x14], [0x14, 0x14], [0x14, 0x15], 
   [0x14, 0x15], [0x15, 0x14], [0x15, 0x14], [0x15, 0x14], 
   [0x16, 0x13], [0x15, 0x15], [0x15, 0x15], [0x15, 0x16], 
   [0x14, 0x18], [0x16, 0x15], [0x16, 0x15], [0x16, 0x15], 
   [0x16, 0x16], [0x16, 0x16], [0x16, 0x16], [0x16, 0x17], 
   [0x15, 0x19], [0x17, 0x16], [0x17, 0x16], [0x18, 0x14], 
   [0x17, 0x17], [0x17, 0x17], [0x17, 0x17], [0x17, 0x18], 
   [0x17, 0x18], [0x17, 0x18], [0x17, 0x19], [0x18, 0x17], 
   [0x18, 0x17], [0x19, 0x16], [0x18, 0x18], [0x18, 0x18], 
   [0x18, 0x19], [0x18, 0x19], [0x19, 0x18], [0x19, 0x18], 
   [0x19, 0x18], [0x1a, 0x17], [0x19, 0x19], [0x19, 0x19], 
   [0x19, 0x1a], [0x18, 0x1c], [0x1a, 0x19], [0x1a, 0x19], 
   [0x1a, 0x19], [0x1a, 0x1a], [0x1a, 0x1a], [0x1a, 0x1a], 
   [0x1a, 0x1b], [0x19, 0x1d], [0x1b, 0x1a], [0x1b, 0x1a], 
   [0x1c, 0x18], [0x1b, 0x1b], [0x1b, 0x1b], [0x1b, 0x1b], 
   [0x1b, 0x1c], [0x1b, 0x1c], [0x1b, 0x1c], [0x1b, 0x1d], 
   [0x1c, 0x1b], [0x1c, 0x1b], [0x1d, 0x1a], [0x1c, 0x1c], 
   [0x1c, 0x1c], [0x1c, 0x1d], [0x1c, 0x1d], [0x1d, 0x1c], 
   [0x1d, 0x1c], [0x1d, 0x1c], [0x1e, 0x1b], [0x1d, 0x1d], 
   [0x1d, 0x1d], [0x1d, 0x1e], [0x1d, 0x1e], [0x1e, 0x1d], 
   [0x1e, 0x1d], [0x1e, 0x1d], [0x1e, 0x1e], [0x1e, 0x1e], 
   [0x1e, 0x1e], [0x1e, 0x1f], [0x1e, 0x1f], [0x1f, 0x1e], 
   [0x1f, 0x1e], [0x1f, 0x1e], [0x1f, 0x1f], [0x1f, 0x1f] ]
   
omatch6 = [ [0x00, 0x00], [0x00, 0x01], [0x01, 0x00], [0x01, 0x01], 
   [0x01, 0x01], [0x01, 0x02], [0x02, 0x01], [0x02, 0x02], 
   [0x02, 0x02], [0x02, 0x03], [0x03, 0x02], [0x03, 0x03], 
   [0x03, 0x03], [0x03, 0x04], [0x04, 0x03], [0x04, 0x04], 
   [0x04, 0x04], [0x04, 0x05], [0x05, 0x04], [0x05, 0x05], 
   [0x05, 0x05], [0x05, 0x06], [0x06, 0x05], [0x00, 0x11], 
   [0x06, 0x06], [0x06, 0x07], [0x07, 0x06], [0x02, 0x10], 
   [0x07, 0x07], [0x07, 0x08], [0x08, 0x07], [0x03, 0x11], 
   [0x08, 0x08], [0x08, 0x09], [0x09, 0x08], [0x05, 0x10], 
   [0x09, 0x09], [0x09, 0x0a], [0x0a, 0x09], [0x06, 0x11], 
   [0x0a, 0x0a], [0x0a, 0x0b], [0x0b, 0x0a], [0x08, 0x10], 
   [0x0b, 0x0b], [0x0b, 0x0c], [0x0c, 0x0b], [0x09, 0x11], 
   [0x0c, 0x0c], [0x0c, 0x0d], [0x0d, 0x0c], [0x0b, 0x10], 
   [0x0d, 0x0d], [0x0d, 0x0e], [0x0e, 0x0d], [0x0c, 0x11], 
   [0x0e, 0x0e], [0x0e, 0x0f], [0x0f, 0x0e], [0x0e, 0x10], 
   [0x0f, 0x0f], [0x0f, 0x10], [0x10, 0x0e], [0x10, 0x0f], 
   [0x11, 0x0e], [0x10, 0x10], [0x10, 0x11], [0x11, 0x10], 
   [0x12, 0x0f], [0x11, 0x11], [0x11, 0x12], [0x12, 0x11], 
   [0x14, 0x0e], [0x12, 0x12], [0x12, 0x13], [0x13, 0x12], 
   [0x15, 0x0f], [0x13, 0x13], [0x13, 0x14], [0x14, 0x13], 
   [0x17, 0x0e], [0x14, 0x14], [0x14, 0x15], [0x15, 0x14], 
   [0x18, 0x0f], [0x15, 0x15], [0x15, 0x16], [0x16, 0x15], 
   [0x1a, 0x0e], [0x16, 0x16], [0x16, 0x17], [0x17, 0x16], 
   [0x1b, 0x0f], [0x17, 0x17], [0x17, 0x18], [0x18, 0x17], 
   [0x13, 0x21], [0x18, 0x18], [0x18, 0x19], [0x19, 0x18], 
   [0x15, 0x20], [0x19, 0x19], [0x19, 0x1a], [0x1a, 0x19], 
   [0x16, 0x21], [0x1a, 0x1a], [0x1a, 0x1b], [0x1b, 0x1a], 
   [0x18, 0x20], [0x1b, 0x1b], [0x1b, 0x1c], [0x1c, 0x1b], 
   [0x19, 0x21], [0x1c, 0x1c], [0x1c, 0x1d], [0x1d, 0x1c], 
   [0x1b, 0x20], [0x1d, 0x1d], [0x1d, 0x1e], [0x1e, 0x1d], 
   [0x1c, 0x21], [0x1e, 0x1e], [0x1e, 0x1f], [0x1f, 0x1e], 
   [0x1e, 0x20], [0x1f, 0x1f], [0x1f, 0x20], [0x20, 0x1e], 
   [0x20, 0x1f], [0x21, 0x1e], [0x20, 0x20], [0x20, 0x21], 
   [0x21, 0x20], [0x22, 0x1f], [0x21, 0x21], [0x21, 0x22], 
   [0x22, 0x21], [0x24, 0x1e], [0x22, 0x22], [0x22, 0x23], 
   [0x23, 0x22], [0x25, 0x1f], [0x23, 0x23], [0x23, 0x24], 
   [0x24, 0x23], [0x27, 0x1e], [0x24, 0x24], [0x24, 0x25], 
   [0x25, 0x24], [0x28, 0x1f], [0x25, 0x25], [0x25, 0x26], 
   [0x26, 0x25], [0x2a, 0x1e], [0x26, 0x26], [0x26, 0x27], 
   [0x27, 0x26], [0x2b, 0x1f], [0x27, 0x27], [0x27, 0x28], 
   [0x28, 0x27], [0x23, 0x31], [0x28, 0x28], [0x28, 0x29], 
   [0x29, 0x28], [0x25, 0x30], [0x29, 0x29], [0x29, 0x2a], 
   [0x2a, 0x29], [0x26, 0x31], [0x2a, 0x2a], [0x2a, 0x2b], 
   [0x2b, 0x2a], [0x28, 0x30], [0x2b, 0x2b], [0x2b, 0x2c], 
   [0x2c, 0x2b], [0x29, 0x31], [0x2c, 0x2c], [0x2c, 0x2d], 
   [0x2d, 0x2c], [0x2b, 0x30], [0x2d, 0x2d], [0x2d, 0x2e], 
   [0x2e, 0x2d], [0x2c, 0x31], [0x2e, 0x2e], [0x2e, 0x2f], 
   [0x2f, 0x2e], [0x2e, 0x30], [0x2f, 0x2f], [0x2f, 0x30], 
   [0x30, 0x2e], [0x30, 0x2f], [0x31, 0x2e], [0x30, 0x30], 
   [0x30, 0x31], [0x31, 0x30], [0x32, 0x2f], [0x31, 0x31], 
   [0x31, 0x32], [0x32, 0x31], [0x34, 0x2e], [0x32, 0x32], 
   [0x32, 0x33], [0x33, 0x32], [0x35, 0x2f], [0x33, 0x33], 
   [0x33, 0x34], [0x34, 0x33], [0x37, 0x2e], [0x34, 0x34], 
   [0x34, 0x35], [0x35, 0x34], [0x38, 0x2f], [0x35, 0x35], 
   [0x35, 0x36], [0x36, 0x35], [0x3a, 0x2e], [0x36, 0x36], 
   [0x36, 0x37], [0x37, 0x36], [0x3b, 0x2f], [0x37, 0x37], 
   [0x37, 0x38], [0x38, 0x37], [0x3d, 0x2e], [0x38, 0x38], 
   [0x38, 0x39], [0x39, 0x38], [0x3e, 0x2f], [0x39, 0x39], 
   [0x39, 0x3a], [0x3a, 0x39], [0x3a, 0x3a], [0x3a, 0x3a], 
   [0x3a, 0x3b], [0x3b, 0x3a], [0x3b, 0x3b], [0x3b, 0x3b], 
   [0x3b, 0x3c], [0x3c, 0x3b], [0x3c, 0x3c], [0x3c, 0x3c], 
   [0x3c, 0x3d], [0x3d, 0x3c], [0x3d, 0x3d], [0x3d, 0x3d], 
   [0x3d, 0x3e], [0x3e, 0x3d], [0x3e, 0x3e], [0x3e, 0x3e], 
   [0x3e, 0x3f], [0x3f, 0x3e], [0x3f, 0x3f], [0x3f, 0x3f] ]
        
def complt_vec4( a, b ):
        return((a.x < b.x) or (a.y < b.y) or (a.z < b.z) or (a.w < b.w))

def set_vec4( v, x, y, z, w ):
    v.x = x
    v.y = y
    v.z = z
    v.w = w
    return v
    
def set1_vec4_const( x ):
    v = vec4_t( x, x, x, x )
    return v    
    
def set1_vec4( v, x ):
    v.x = x
    v.y = x
    v.z = x
    v.w = x
    return v

def rcp_vec4( v ):   
    one = vec4_t( 1.0, 1.0, 1.0, 1.0 );
    return (one / v)

def min_vec4( a, b ):
    return set_vec4( a, min( a.x, b.x ), min( a.y, b.y ), min( a.z, b.z ), min( a.w, b.w ) )
    
def max_vec4( a, b ):
    return set_vec4( a, max( a.x, b.x ), max( a.y, b.y ), max( a.z, b.z ), max( a.w, b.w ) )
    
def min_vec4_embedded( a, b ):
    return set_vec4( a, min( a.x, b.x ), min( a.y, b.y ), min( a.z, b.z ), min( a.w, b.w ) )
    
def max_vec4_embedded( a, b ):
    return set_vec4( a, max( a.x, b.x ), max( a.y, b.y ), max( a.z, b.z ), max( a.w, b.w ) )

def accum_vec4( v ):
    return (v.x + v.y + v.z + v.w)

def dot_vec4( a, b ):
    return accum_vec4(a * b)
    
def splatz_vec4( v ):
    v.x = v.z
    v.y = v.z
    v.w = v.z
    return v

def trunc_vec4( v ):
   
   v0 = 0.0
   v1 = 0.0
   v2 = 0.0
   v3 = 0.0
   
   if v.x > 0.0:
       v0 = math.floor(v.x)
   else:
       v0 = math.ceil(v.x)
       
   if v.y > 0.0:
       v1 = math.floor(v.y)
   else:
       v1 = math.ceil(v.y)
       
   if v.z > 0.0:
       v2 = math.floor(v.z)
   else:
       v2 = math.ceil(v.z)
       
   if v.w > 0.0:
       v3 = math.floor(v.w)
   else:
       v3 = math.ceil(v.w)
   
   r = vec4_t( v0, v1, v2, v3 )
   
   return r

def swap( a, b ):
    t = 0
    t = a
    a = b
    b = t

class dxtblock:
    """DXT block class"""
    
    def __init__( self ):
        self.single = 0;
        self.alphamask = 0;
        self.points = [ vec4_t() ] * 16;
        self.palette = [ vec4_t() ] * 4;
        self.max = vec4_t();
        self.min = vec4_t();
        self.metric = vec4_t();

def getlong24( buf, p = 0 ):
    return (((buf)[p]) | ((buf)[p+1] <<  8) | ((buf)[p+2] << 16))
    
def getlong24_int( buf ):
    return buf | (buf << 8 | buf << 16)
    
def putlong16( buf, s, pos ):
    buf[pos]   = ( ( s )      ) & 0xff
    buf[pos+1]   = ( ( s ) >> 8 ) & 0xff

    # buf[0] = ((s)) & 0xff
    # buf[1] = ((s) >> 8) & 0xff
    
def putlong32( buf, l, pos ):
    buf[pos]   = ( ( l ) ) & 0xff
    buf[pos+1] = ( ( l ) >> 8 ) & 0xff
    buf[pos+2] = ( ( l ) >> 16 ) & 0xff
    buf[pos+3] = ( ( l ) >> 24 ) & 0xff

def compress_BC1( dest, src, w, h, flags ):
    
    block_num = block_count(w, h)
    block = np.empty( 64, dtype=np.ubyte )
    
    for i in range( 1, block_num ):
        x = int(i % ((w + 3) >> 2)) << 2;
        y = int(i / ((w + 3) >> 2)) << 2;
        
        #p = np.empty( block_offset(x, y, w, 8), dtype=np.ubyte )
        
        extract_block(src, x, y, w, h, block);
        
        pos = block_offset(x, y, w, 8)
        
        encode_color_block(dest, block, DXT_BC1 | flags, pos);

def convert_pixels( dest, src, format, w, h, d, bpp, palette, mipmaps ):
    num_pixels = 0
    r = 0
    g = 0
    b = 0
    a = 0
    
    print( 'converting pixels... bpp {}'.format( bpp ) )

    num_pixels = get_mipmapped_size(w, h, 1, 0, mipmaps, DDS_COMPRESS_NONE);

    for i in range( 0, num_pixels ):
        if bpp == 1:
            if palette:
                r = palette[3 * src[i] + 0]
                g = palette[3 * src[i] + 1]
                b = palette[3 * src[i] + 2]
            else:
                r = g = b = src[i]

            if format == DDS_FORMAT_A8:
                a = src[i]
            else:
                a = 255
        elif bpp == 2:
            r = g = b = src[2 * i];
            a = src[2 * i + 1];
        elif bpp == 3:
            b = src[3 * i + 0];
            g = src[3 * i + 1];
            r = src[3 * i + 2];
            a = 255;
        else:
            b = src[4 * i + 0];
            g = src[4 * i + 1];
            r = src[4 * i + 2];
            a = src[4 * i + 3];

        match format:
            case 1:
                dest[3 * i + 1] = g;
                dest[3 * i + 2] = r;
                dest[3 * i + 0] = b;
                break;
            case 2:
                dest[4 * i + 0] = b;
                dest[4 * i + 1] = g;
                dest[4 * i + 2] = r;
                dest[4 * i + 3] = a;
                break;
            case 3:
                dest[3 * i + 0] = r;
                dest[3 * i + 1] = g;
                dest[3 * i + 2] = b;
                break;
            case 4:
                dest[4 * i + 0] = r;
                dest[4 * i + 1] = g;
                dest[4 * i + 2] = b;
                dest[4 * i + 3] = a;
                break;
            case 5:
                putlong16(dest[2 * i], pack_r5g6b5(r, g, b));
                break;
            case 6:
                putlong16(dest[2 * i], pack_rgba4(r, g, b, a));
                break;
            case 7:
                putlong16(dest[2 * i], pack_rgb5a1(r, g, b, a));
                break;
            case 8:
                putlong32(dest[4 * i], pack_rgb10a2(r, g, b, a));
                break;
            case 9:
                dest[i] = pack_r3g3b2(r, g, b);
                break;
            case 10:
                dest[i] = a;
                break;
            case 11:
                dest[i] = rgb_to_luminance(r, g, b);
                break;
            case 12:
                dest[2 * i + 0] = rgb_to_luminance(r, g, b);
                dest[2 * i + 1] = a;
                break;
            case 13:
                dest[4 * i] = a;
                RGB_to_YCoCg(dest[4 * i], r, g, b);
                break;
            case 14:
                alpha_exp(dest[4 * i], r, g, b, a);
                break;
            case _:
                break;


def extract_block( src, x, y, w, h, block ):
    bw = min(w - x, 4)
    bh = min(h - y, 4)
    rem = [0, 0, 0, 0,
    0, 1, 0, 1,
    0, 1, 2, 0,
    0, 1, 2, 3]
    
    #print( 'extracting DXT block x: {} y: {} w: {} h: {}'.format( x, y, w, h ) )
    
    # for(i = 0; i < 4; ++i)
    # {
        # by = rem[(bh - 1) * 4 + i] + y;
        # for(j = 0; j < 4; ++j)
        # {
            # bx = rem[(bw - 1) * 4 + j] + x;
            # block[(i * 4 * 4) + (j * 4) + 0] =
            # src[(by * (w * 4)) + (bx * 4) + 0];
            # block[(i * 4 * 4) + (j * 4) + 1] =
            # src[(by * (w * 4)) + (bx * 4) + 1];
            # block[(i * 4 * 4) + (j * 4) + 2] =
            # src[(by * (w * 4)) + (bx * 4) + 2];
            # block[(i * 4 * 4) + (j * 4) + 3] =
            # src[(by * (w * 4)) + (bx * 4) + 3];
        # }
    # }
    
    for i in range( 0, 4 ):
        by = rem[(bh - 1) * 4 + i] + y;
        for j in range( 0, 4 ):
            bx = rem[(bw - 1) * 4 + j] + x;
            block[(i * 4 * 4) + (j * 4) + 0] = src[(by * (w * 4)) + (bx * 4) + 0];
            block[(i * 4 * 4) + (j * 4) + 1] = src[(by * (w * 4)) + (bx * 4) + 1];
            block[(i * 4 * 4) + (j * 4) + 2] = src[(by * (w * 4)) + (bx * 4) + 2];
            block[(i * 4 * 4) + (j * 4) + 3] = src[(by * (w * 4)) + (bx * 4) + 3];

def get_mipmapped_size( width, height, bpp, level, num, format ):
    w = 0
    h = 0
    n = 0
    size = 0

    w = width >> level
    h = height >> level
    w = max(1, w)
    h = max(1, h)
    w <<= 1
    h <<= 1

    while n < num and (w != 1 or h != 1):
        if(w > 1): w >>= 1
        if(h > 1): h >>= 1
        if(format == DDS_COMPRESS_NONE):
            size += (w * h)
        else:
            size += ((w + 3) >> 2) * ((h + 3) >> 2)
        n += 1;

    if format == DDS_COMPRESS_NONE:
        size *= bpp
    else:
        if format == DDS_COMPRESS_BC1 or format == DDS_COMPRESS_BC4:
            size *= 8;
        else:
            size *= 16;

    return(size)

def dxt_compress( dest, src, format, width, height, bpp, mipmaps, flags ):
    size = 0
    tmp = None
    s = 0
    offset = 0

    if bpp == 1:
        # grayscale promoted to BGRA

        size = get_mipmapped_size(width, height, 4, 0, mipmaps, DDS_COMPRESS_NONE)
        tmp = np.empty(size, dtype=np.ubyte)

        i = 0

        while True:
            for j in range( 0, size, 4 ):
                tmp[j + 0] = src[i];
                tmp[j + 1] = src[i];
                tmp[j + 2] = src[i];
                tmp[j + 3] = 255;
                i += 1
            break

        bpp = 4;

    elif bpp == 2:
        # gray-alpha promoted to BGRA

        size = get_mipmapped_size(width, height, 4, 0, mipmaps, DDS_COMPRESS_NONE)
        tmp = np.empty(size, dtype=np.ubyte)
        i = 0

        while True:
            for j in range( 0, size, 4 ):
                tmp[j + 0] = src[i];
                tmp[j + 1] = src[i];
                tmp[j + 2] = src[i];
                tmp[j + 3] = src[i + 1];
                i += 2
            break

        bpp = 4;

    elif bpp == 3:
        size = get_mipmapped_size(width, height, 4, 0, mipmaps, DDS_COMPRESS_NONE)
        tmp = np.empty(size, dtype=np.ubyte)
        i = 0

        while True:
            for j in range( 0, size, 4 ):
                tmp[j + 0] = src[i + 0]
                tmp[j + 1] = src[i + 1]
                tmp[j + 2] = src[i + 2]
                tmp[j + 3] = 255
                i += 3
            break

        bpp = 4

    curpos = 0
    w = width;
    h = height;
    s = None
    
    if tmp != None and tmp.any():
        s = tmp
    else: 
        s = src
    
    if format > DDS_COMPRESS_NONE:
        match format:
            case 1:
                print('compressing to DXT1...')
                compress_BC1(dest, s, w, h, flags)
            case 2:
                compress_BC2(dest, s, w, h, flags)
            case 3:
                compress_BC3(dest, s, w, h, flags)
            case 4:
                compress_BC3(dest, s, w, h, flags)
            case 5:
                compress_BC3(dest, s, w, h, flags)
            case 6:
                compress_BC3(dest, s, w, h, flags)
            case 7:
                compress_BC3(dest, s, w, h, flags)
            case 8:
                compress_BC4(dest, s, w, h)
            case 9:
                compress_BC5(dest, s, w, h)
            case 10:
                compress_YCoCg(dest, s, w, h)
            case _:
                compress_BC3(dest, s, w, h, flags)
    
    w = max(1, w >> 1);
    h = max(1, h >> 1);

    if tmp != None and tmp.any(): del tmp

def construct_palette3( dxtb ):
    dxtb.palette[0] = dxtb.max
    dxtb.palette[1] = dxtb.min
    dxtb.palette[2] = (dxtb.max * V4HALF) + (dxtb.min * V4HALF)
    dxtb.palette[3] = vec4_t()
   
def construct_palette4( dxtb ):
    dxtb.palette[0] = dxtb.max;
    dxtb.palette[1] = dxtb.min;
    dxtb.palette[2] = ( dxtb.max * V4TWOTHIRDS ) + ( dxtb.min * V4ONETHIRD );
    dxtb.palette[3] = ( dxtb.max * V4ONETHIRD ) + ( dxtb.min * V4TWOTHIRDS );
   
def match_colors3( dxtb ):
    idx = 0
    indices = 0;
    t0 = vec4_t()
    t1 = vec4_t()
    t2 = vec4_t()
    d0 = 0.0
    d1 = 0.0
    d2 = 0.0

    # match each point to the closest color
    for i in range( 0, 16 ):
        # skip alpha pixels
        if(((dxtb.alphamask >> (2 * i)) & 3) == 3):
            indices |= (3 << (2 * i));
            continue;

        t0 = (dxtb.points[i] - dxtb.palette[0]) * dxtb.metric;
        t1 = (dxtb.points[i] - dxtb.palette[1]) * dxtb.metric;
        t2 = (dxtb.points[i] - dxtb.palette[2]) * dxtb.metric;

        d0 = dot_vec4(t0, t0);
        d1 = dot_vec4(t1, t1);
        d2 = dot_vec4(t2, t2);

        if((d0 < d1) and (d0 < d2)):
            idx = 0
        elif(d1 < d2):
            idx = 1
        else:
            idx = 2

        indices |= (idx << (2 * i));

    return indices

def match_colors4( dxtb ):
    idx = 0
    indices = 0
    b0 = 0
    b1 = 0
    b2 = 0
    b3 = 0
    b4 = 0
    x0 = 0
    x1 = 0
    x2 = 0
    t0 = vec4_t()
    t1 = vec4_t()
    t2 = vec4_t()
    t3 = vec4_t()

    d = [ 0.0, 0.0, 0.0, 0.0 ]

    # match each point to the closest color
    for i in range( 0, 16 ):
        t0 = (dxtb.points[i] - dxtb.palette[0]) * dxtb.metric;
        t1 = (dxtb.points[i] - dxtb.palette[1]) * dxtb.metric;
        t2 = (dxtb.points[i] - dxtb.palette[2]) * dxtb.metric;
        t3 = (dxtb.points[i] - dxtb.palette[3]) * dxtb.metric;

        d[0] = dot_vec4(t0, t0);
        d[1] = dot_vec4(t1, t1);
        d[2] = dot_vec4(t2, t2);
        d[3] = dot_vec4(t3, t3);

        b0 = d[0] > d[3];
        b1 = d[1] > d[2];
        b2 = d[0] > d[2];
        b3 = d[1] > d[3];
        b4 = d[2] > d[3];

        x0 = b1 & b2;
        x1 = b0 & b3;
        x2 = b0 & b4;

        idx = x2 | ((x0 | x1) << 1);

        indices |= (idx << (2 * i));

    return indices;

def optimize_endpoints3( dxtb, indices, max, min ):
    alpha = 0.0
    beta = 0.0
    alpha2_sum = vec4_t()
    alphax_sum = vec4_t()
    beta2_sum = vec4_t()
    betax_sum = vec4_t()
    alphabeta_sum = vec4_t() 
    a = vec4_t() 
    b = vec4_t() 
    factor = vec4_t()
    bits = 0

    for i in range( 0, 16 ):
        bits = indices >> (2 * i);

        # skip alpha pixels
        if((bits & 3) == 3): continue;

        beta = (bits & 1);
        if (bits & 2): beta = 0.5;
        alpha = 1.0 - beta;

        a = set1_vec4(a, alpha);
        b = set1_vec4(b, beta);
        alpha2_sum += a * a;
        beta2_sum += b * b;
        alphabeta_sum += a * b;
        alphax_sum += dxtb.points[i] * a;
        betax_sum  += dxtb.points[i] * b;

    factor = alpha2_sum * beta2_sum - alphabeta_sum * alphabeta_sum;
    if(complt_vec4(factor, V4EPSILON)): return;
    factor = rcp_vec4(factor);
 
    a = (alphax_sum * beta2_sum  - betax_sum  * alphabeta_sum) * factor;
    b = (betax_sum  * alpha2_sum - alphax_sum * alphabeta_sum) * factor;

    # clamp to the color space
    a = min_vec4(V4ONE, max_vec4(V4ZERO, a));
    b = min_vec4(V4ONE, max_vec4(V4ZERO, b));
    a = trunc_vec4(V4GRID * a + V4HALF) * V4GRIDRCP;
    b = trunc_vec4(V4GRID * b + V4HALF) * V4GRIDRCP;

    max = a;
    min = b;

def compress3( dxtb ):
    import sys
    
    MAX_ITERATIONS = 8
    indices = 0
    bestindices = 0
    error = 0.0
    besterror = sys.float_info.max
    oldmax = vec4_t()
    oldmin = vec4_t()

    construct_palette3(dxtb);

    indices = match_colors3(dxtb);
    bestindices = indices;

    for i in range( 0, MAX_ITERATIONS ):
        oldmax = dxtb.max;
        oldmin = dxtb.min;

        optimize_endpoints3( dxtb, indices, dxtb.max, dxtb.min );
        construct_palette3( dxtb );
        indices = match_colors3( dxtb );
        error = compute_error3( dxtb, indices );

        if(error < besterror):
            besterror = error;
            bestindices = indices;
        else:
            dxtb.max = oldmax;
            dxtb.min = oldmin;
            break;

    return(bestindices);
    
def compute_error3( dxtb, indices ):
    idx = 0
    error = 0;
    t = vec4_t()
    error = 0

   # compute error
    for i in range( 0, 16 ):
        idx = (indices >> (2 * i)) & 3;
        # skip alpha pixels
        if(idx == 3): continue;
        t = (dxtb.points[i] - dxtb.palette[idx]) * dxtb.metric;
        error += dot_vec4(t, t);

    return error;
    
def compute_error4( block, indices ):
    
    t = vec4_t()
    error = 0
    
    for i in range( 0, 16 ):
        idx = (indices >> (2 * i)) & 3;
        t = (block.points[i] - block.palette[idx]) * block.metric;
        error += dot_vec4(t, t);
        
    return error
    
def compress4( dxtb ):
    import sys
    
    MAX_ITERATIONS = 8;
    indices = 0 
    bestindices = 0
    error = sys.float_info.max
    besterror = sys.float_info.max;
    oldmax = vec4_t()
    oldmin = vec4_t()

    construct_palette4( dxtb );

    indices = match_colors4( dxtb );
    bestindices = indices;

    for i in range( 0, MAX_ITERATIONS ):
        oldmax = dxtb.max;
        oldmin = dxtb.min;

        optimize_endpoints4(dxtb, indices, dxtb.max, dxtb.min);
        construct_palette4(dxtb);
        indices = match_colors4(dxtb);
        error = compute_error4(dxtb, indices);

        if(error < besterror):
            besterror = error;
            bestindices = indices;
        else:
            dxtb.max = oldmax;
            dxtb.min = oldmin;
            break;

    return bestindices

   
def optimize_endpoints4( dxtb, indices, max, min ):
    
    alpha = 0.0
    beta = 0.0
    alpha2_sum = vec4_t()
    alphax_sum = vec4_t()
    beta2_sum = vec4_t()
    betax_sum = vec4_t()
    alphabeta_sum = vec4_t()
    a = vec4_t()
    b = vec4_t()
    factor = vec4_t()
    bits = 0

    for i in range( 0, 16 ):
        bits = indices >> (2 * i);

        beta = (bits & 1);
        if(bits & 2): beta = (1.0 + beta) / 3.0;
        alpha = 1.0 - beta;

        a = set1_vec4_const(alpha);
        b = set1_vec4_const(beta);
        alpha2_sum += a * a;
        beta2_sum += b * b;
        alphabeta_sum += a * b;
        alphax_sum += dxtb.points[i] * a;
        betax_sum  += dxtb.points[i] * b;

    factor = alpha2_sum * beta2_sum - alphabeta_sum * alphabeta_sum;
    if(complt_vec4(factor, V4EPSILON)): return
    factor = rcp_vec4(factor);

    a = (alphax_sum * beta2_sum  - betax_sum  * alphabeta_sum) * factor;
    b = (betax_sum  * alpha2_sum - alphax_sum * alphabeta_sum) * factor;

    # clamp to the color space
    a = min_vec4(V4ONE, max_vec4(V4ZERO, a));
    b = min_vec4(V4ONE, max_vec4(V4ZERO, b));
    a = trunc_vec4(V4GRID * a + V4HALF) * V4GRIDRCP;
    b = trunc_vec4(V4GRID * b + V4HALF) * V4GRIDRCP;

    max = a;
    min = b;

def dxtblock_init( dxtb, block, flags ):
    i = 0
    c0 = 0
    c = 0
    bc1 = (flags & DXT_BC1)
    x = 0.0
    y = 0.0
    z = 0.0
    min1 = vec4_t(1.0, 1.0, 1.0, 1.0)
    max1 = vec4_t()
    center = vec4_t()
    t = vec4_t()
    cov = vec4_t()
    inset = vec4_t()

    dxtb.single = 1;
    dxtb.alphamask = 0;

    if(flags & DXT_PERCEPTUAL):
        # ITU-R BT.709 luma coefficents
        set_vec4(dxtb.metric, 0.2126, 0.7152, 0.0722, 0.0)
    else:
        set_vec4(dxtb.metric, 1.0, 1.0, 1.0, 0.0)

    c0 = getlong24(block);

    for i in range( 0, 16 ):
        
        if bc1 and (block[4 * i + 3] < 128):
            dxtb.alphamask |= (3 << (2 * i))

        x = block[4 * i + 0] / 255.0
        y = block[4 * i + 1] / 255.0
        z = block[4 * i + 2] / 255.0

        set_vec4(dxtb.points[i], x, y, z, 0.0)

        c = getlong24(block, 4 * i)
        
        if dxtb.single and (c == c0): dxtb.single = 1

    # no need to continue if this is a single color block
    if (dxtb.single > 0): return

    set1_vec4( min1, 1.0 );
    #max = vec4_zero();

    # get bounding box extents
    for i in range( 0, 16 ):
        min_vec4( min1, dxtb.points[i] )
        max_vec4( max1, dxtb.points[i] )

    # select diagonal  
    center = (max1 + min1) * V4HALF;

    #cov = vec4_zero();
    for i in range( 0, 16 ):
        for j in range( 0, 4 ):
            t = dxtb.points[i] - center
            cov += t * splatz_vec4(t)

    x0 = max1.x;
    y0 = max1.y;
    x1 = min1.x;
    y1 = min1.y;

    if(cov.x < 0): swap(x0, x1);
    if(cov.y < 0): swap(y0, y1);

    max1.x = x0;
    max1.y = y0;
    min1.x = x1;
    min1.y = y1;

    # inset bounding box and clamp to [0,1]
    
    inset = (max1 - min1) * set1_vec4_const(1.0 / 16.0) - set1_vec4_const((8.0 / 255.0) / 16.0);
    max1 = min_vec4(V4ONE, max_vec4(V4ZERO, max1 - inset));
    min1 = min_vec4(V4ONE, max_vec4(V4ZERO, min1 + inset));

    # clamp to color space and save
    dxtb.max = trunc_vec4(V4GRID * max1 + V4HALF) * V4GRIDRCP;
    dxtb.min = trunc_vec4(V4GRID * min1 + V4HALF) * V4GRIDRCP;

def vec4_endpoints_to_565( start, end, a, b ):
    c = np.empty( 8, dtype=np.int16)
    
    ta = a * V4GRID + V4HALF
    tb = b * V4GRID + V4HALF
    
    c[0] = int(ta.x)
    c[1] = int(ta.y)
    c[2] = int(ta.z)
    c[4] = int(tb.x)
    c[5] = int(tb.y)
    c[6] = int(tb.z)
    c[0] = min(31, max(0, c[0]));
    c[1] = min(63, max(0, c[1]));
    c[2] = min(31, max(0, c[2]));
    c[4] = min(31, max(0, c[4]));
    c[5] = min(63, max(0, c[5]));
    c[6] = min(31, max(0, c[6]));
    
    start = (((c[2]) << 11) | ((c[1]) << 5) | (c[0]))
    end   = (((c[6]) << 11) | ((c[5]) << 5) | (c[4]))

def encode_color_block( dest, block, flags, pos ):
    dxtb = dxtblock()
    max16 = 0
    min16 = 0
    indices = 0
    mask = 0

    dxtblock_init(dxtb, block, flags);

    if dxtb.single == 1: # single color block
        
        max16 = ( omatch5[block[2]][0] << 11 ) | ( omatch6[block[1]][0] << 5 ) | ( omatch5[block[0]][0] );
        min16 = ( omatch5[block[2]][1] << 11 ) | ( omatch6[block[1]][1] << 5 ) | ( omatch5[block[0]][1] );

        #indices = 0x55555555; # 101010...
        indices = 0xaaaaaaaa; # 101010...

        if (flags & DXT_BC1) and dxtb.alphamask:
            # DXT1 compression, non-opaque block.  Add alpha indices.
            indices |= dxtb.alphamask
            
            if(max16 > min16):
                swap(max16, min16)
        elif max16 < min16:
            swap(max16, min16);
            
            #indices ^= 0x55555555; # 010101...
            #indices ^= 0xaaaaaaaa; # 010101...

    elif (flags & DXT_BC1) and dxtb.alphamask: # DXT1 compression, non-opaque block
        indices = compress3(dxtb);

        vec4_endpoints_to_565(max16, min16, dxtb.max, dxtb.min);

        if(max16 > min16):
            swap(max16, min16);
            # remap indices 0 . 1, 1 . 0
            mask = indices & 0xaaaaaaaa;
            mask = mask | (mask >> 1);
            indices = (indices & mask) | ((indices ^ 0x55555555) & ~mask);
    else:
        indices = compress4(dxtb);

        vec4_endpoints_to_565(max16, min16, dxtb.max, dxtb.min);

        if(max16 < min16):
            swap(max16, min16)
            indices ^= 0x55555555 # 010101...

    putlong16( dest, max16, pos )
    putlong16( dest, min16, pos+2 )
    putlong32( dest, indices, pos+4 )
