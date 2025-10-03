#############################################
# THPS TEX (.tex) IMPORT/EXPORT
#############################################
import bpy
import os
import struct
import platform
from bpy.props import *
from . constants import *
from . helpers import *

# METHODS
#############################################
import math
import numpy as np

from . dxt import *
import subprocess

# Get or generate a new image, given the image name/dimensions
def get_image(img_name, img_width, img_height):
    if not bpy.data.images.get(img_name):
        bpy.ops.image.new(name=img_name, width=img_width, height=img_height)
        image = bpy.data.images[img_name]
    else:
        image = bpy.data.images.get(img_name)
    return image
    
# Returns an image object or None if there is no image found
def maybe_get_image(img_name):
    if not bpy.data.images.get(img_name):
        return None
    return bpy.data.images.get(img_name)

# Get or generate a new texture, given the texture name
def get_texture(tex_name):
    if not bpy.data.textures.get(tex_name):
        blender_tex = bpy.data.textures.new(tex_name, "IMAGE")
    else:
        blender_tex = bpy.data.textures.get(tex_name)
    return blender_tex
    
def np_from_image(img):
    return np.array(img.pixels[:])

# Flattens RGB data from pixels into a single grayscale channel
def rgb_to_grayscale(pixels):
    channel_r = pixels[0::4]
    channel_g = pixels[1::4]
    channel_b = pixels[2::4]
    return (channel_r + channel_g + channel_b) / 3.0
    
def clear_img_channel(img, chn):
    img_pixels = np_from_image(img)
    channels = [ 'r', 'g', 'b', 'a' ]
    channel_num = channels.index(chn)
    img_pixels[channel_num::4] = 0.0
    img.pixels = img_pixels.tolist()
    del img_pixels
    
def invert_img_channel(img_pixels, chn):
    channels = [ 'r', 'g', 'b', 'a' ]
    channel_num = channels.index(chn)
    img_pixels[channel_num::4] = [ (255 - x) for x in img_pixels[channel_num::4] ]
    return img_pixels

# Replaces a color channel of one texture with those of another
def replace_img_channel(source_img, mix_img, chn):
    channels = [ 'r', 'g', 'b', 'a' ]
    channel_num = channels.index(chn)
    pixels = np_from_image(source_img)
    pixels2 = np_from_image(mix_img)
    pixels[channel_num::4] = rgb_to_grayscale(pixels2)
    source_img.pixels = pixels.tolist()
    source_img.update()

#----------------------------------------------------------------------------------
#- Missi: Completely rewritten. Old function was wholly reliant on the old BGL API
#----------------------------------------------------------------------------------
def get_all_compressed_mipmaps(image, compression_type, mm_offset, folder):
    import math, os
    import numpy as np
    from contextlib import ExitStack
    assert image.channels == 4
    assert compression_type in (1, 5)

    uncompressed_data = get_all_mipmaps(image, mm_offset)
    if not uncompressed_data: return []

    textures = []
    
    dxt_compressor = "dxtcompressor.exe" if platform.system() == "Windows" else "dxtcompressor"

        #src_uint8 = np.empty( len( uncompressed_pixels.pixels ), dtype=np.uint8 )

        #out_bytes = None

    for level, (uncomp_w, uncomp_h, uncompressed_pixels) in enumerate(uncompressed_data):

        src = np.empty( len( uncompressed_pixels.pixels ), dtype=np.float32 )
        #src_uint8 = np.empty( len( uncompressed_pixels.pixels ), dtype=np.uint8 )

        out_bytes = None
        
        uncompressed_pixels.pixels.foreach_get( src )

        #for i in range( 0, len( src ) ):
            #src_uint8[i] = ( src[i] * 255.0 )
        
        #swap_rb( src_uint8, uncomp_w * uncomp_h, 4 )
        
        #convert_pixels( fmtdst, src, DDS_FORMAT_RGBA8, uncomp_w, uncomp_h, 0, 4, None, 1 )
        
        path = '{0}{1}{2}_mip{3}.ddsbytes'.format( folder, os.sep, image.name, level )

        try:
            fd = os.open( path, os.O_RDONLY )
            #LOG.debug( 'file {} already exists!'.format( path ) )
            os.close( fd )
        except OSError as e:
            #LOG.debug( 'creating file {}'.format( path ) )
            fd = os.open( path, os.O_WRONLY | os.O_CREAT )
            os.write( fd, src )
            os.close( fd )

        #dxt_compress( out_bytes, src_uint8, DDS_COMPRESS_BC1, uncomp_w, uncomp_h, 4, 1, 0 )
        
        out_path = '{0}{1}{2}_mip{3}.ddscache'.format( folder, os.sep, image.name, level )

        subprocess.run( [ get_asset_path( dxt_compressor ), path, '{0}'.format( uncomp_w ), '{0}'.format( uncomp_h ), '{0}'.format( compression_type ), out_path ], capture_output=True )

        with open(out_path, "rb" ) as file:
            out_bytes = file.read()
            
        #os.remove( '{0}{1}{2}_mip{3}.ddsbytes'.format( folder, os.sep, image.name, level ) )

        if ( out_bytes == None ):
            LOG.debug( "uh oh... " )
            return None

        textures.append( ( uncomp_w, uncomp_h, out_bytes ) )
    
    return textures

#----------------------------------------------------------------------------------
#- Missi: Completely rewritten. Old function was wholly reliant on the old BGL API
#----------------------------------------------------------------------------------
def get_all_mipmaps(image, mm_offset = 0):
    
    textures = []
    base_width = image.size[0]
    base_height = image.size[1]
    
    image_width = base_width
    image_height = base_height
    
    for iterations in range( 0, image.thug_image_props.mip_levels ):

        src = bpy.data.images.new( '{}_mip{}_compressed'.format( image.name, iterations ), base_width, base_height )
        
        new_pixels = np.empty( len( image.pixels ), dtype=np.float32 )
        
        image.pixels.foreach_get( new_pixels )
        
        src.pixels.foreach_set( new_pixels )

        src.scale( int( image_width ), int( image_height ) )
        src.update()
        
        textures.append( ( int( image_width ), int( image_height ), src ) )

        image_width /= 2.0
        image_height /= 2.0
    
    return textures

#----------------------------------------------------------------------------------
def import_img(path, img_name):
    import bgl
    p = Printer()
    p.on = True
    p("Opening IMG file {}...", path)
    with open(os.path.join(path), "rb") as inp:
        r = Reader(inp.read())
        img_version = p("  version: {}", r.u32())
        p("  file size?: {}", r.u32())
        pal_depth = 32
        img_width = p("  width: {}", r.u32())
        img_height = p("  height: {}", r.u32())
        # Not sure anything in the second half of the header is useful
        r.u32()
        r.u32()
        img_width = p("  width: {}", r.u16())
        img_height = p("  height: {}", r.u16())
        pal_size = p("  pal size: {}", r.u32())
        dxt_version = 5
        is_compressed = True if pal_size > 0 else False
        p("Compressed: {}", is_compressed)
        p("Offset: {}", r.offset)
        
        #if pal_depth == 32:
        if is_compressed:
            pal_colors = []
            for j in range(pal_size // 4):
                cb, cg, cr, ca = r.read("4B")
                pal_colors.append((cr/255.0, cg/255.0, cb/255.0, ca/255.0))
        
                    
        data_size = r.length - r.offset  # The current position is the length
        p("data size: {}", data_size)
        
        data_bytes = r.buf[r.offset:r.offset+data_size]
        
        if is_compressed:
            data_bytes = swizzle(data_bytes, img_width, img_height, 8, 0, True)
            blend_img = bpy.data.images.new(img_name, img_width, img_height, alpha=True)
            blend_img.pixels = [pal_col for pal_idx in data_bytes for pal_col in pal_colors[pal_idx]]
        else:
            colors = []
            for i in range(len(data_bytes) // 4):
                idx = i*4
                cb = data_bytes[idx + 0] / 255.0
                cg = data_bytes[idx + 1] / 255.0
                cr = data_bytes[idx + 2] / 255.0
                ca = data_bytes[idx + 3] / 255.0
                colors.append(cr)
                colors.append(cg)
                colors.append(cb)
                colors.append(ca)
            blend_img = bpy.data.images.new(img_name, img_width, img_height, alpha=True)
            blend_img.pixels = colors
    
    blend_img.pack()
    return blend_img
        
def read_tex(reader, printer):
    import bgl
    global name_format
    r = reader
    p = printer

    p("tex file version: {}", r.i32())
    num_textures = p("num textures: {}", r.i32())

    already_seen = set()

    for i in range(num_textures):
        p("texture #{}", i)
        checksum = p("  checksum: {}", to_hex_string(r.u32()))

        if checksum in already_seen:
            p("Duplicate checksum!", None)
        else:
            already_seen.add(checksum)

        create_image = (checksum not in bpy.data.images)
        if not create_image:
            p("Image {} already exists, will not be created!", checksum)
            
        # tex_map[checksum] = i

        img_width = p("  width: {}", r.u32())
        img_height = p("  height: {}", r.u32())
        levels = p("  levels: {}", r.u32())
        texel_depth = p("  texel depth: {}", r.u32())
        pal_depth = p("  palette depth: {}", r.u32())
        dxt_version = p("  dxt version: {}", r.u32())
        pal_size = p("  palette depth: {}", r.u32())

        if dxt_version == 2:
            dxt_version = 1

        if pal_size > 0:
            if pal_depth == 32:
                pal_colors = []
                for j in range(pal_size//4):
                    cb, cg, cr, ca = r.read("4B")
                    pal_colors.append((cr/255.0, cb/255.0, cb/255.0, ca/255.0))
            else:
                r.read(str(pal_size) + "B")

        for j in range(levels):
            data_size = r.u32()
            
            if not create_image: 
                r.offset += data_size
                continue
                
            if j == 0 and dxt_version == 0:
                data_bytes = r.buf[r.offset:r.offset+data_size]
                if pal_size > 0 and pal_depth == 32 and texel_depth == 8:
                    data_bytes = swizzle(data_bytes, img_width, img_height, 8, 0, True)
                    blend_img = bpy.data.images.new(str(checksum), img_width, img_height, alpha=True)
                    blend_img.pixels = [pal_col for pal_idx in data_bytes for pal_col in pal_colors[pal_idx]]
                    blend_img.thug_image_props.mip_levels = levels
            elif j == 0 and dxt_version in (1, 5):  
                data_bytes = r.buf[r.offset:r.offset+data_size]
                blend_img = bpy.data.images.new(str(checksum), img_width, img_height, alpha=True)
                blend_img.gl_load()
                blend_img.thug_image_props.compression_type = "DXT5" if dxt_version == 5 else "DXT1"
                blend_img.thug_image_props.mip_levels = levels
                image_id = blend_img.bindcode
                if image_id == 0:
                    print("Got 0 bindcode for " + blend_img.name)
                else:
                    buf = bgl.Buffer(bgl.GL_BYTE, len(data_bytes))
                    buf[:] = data_bytes
                    bgl.glBindTexture(bgl.GL_TEXTURE_2D, image_id)
                    bgl.glCompressedTexImage2D(
                        bgl.GL_TEXTURE_2D,
                        0,
                        COMPRESSED_RGBA_S3TC_DXT5_EXT if dxt_version == 5 else COMPRESSED_RGBA_S3TC_DXT1_EXT,
                        img_width, #level_img_width,
                        img_height, #level_img_height,
                        0,
                        len(data_bytes),
                        buf)
                    del buf

                    buf_size = img_width * img_height * 4
                    # LOG.debug(buf_size)
                    buf = bgl.Buffer(bgl.GL_FLOAT, buf_size)
                    bgl.glGetTexImage(bgl.GL_TEXTURE_2D, 0, bgl.GL_RGBA, bgl.GL_FLOAT, buf)
                    blend_img.pixels = buf
                    blend_img.pack()
                    del buf

            r.offset += data_size
            

def get_colortex(color):
    colortex_name = 'io_thps_scene_Color_' + ''.join('{:02X}'.format(int(255*a)) for a in color)
    if bpy.data.images.get(colortex_name):
        return bpy.data.images.get(colortex_name)
    size = 16, 16
    img = bpy.data.images.new(name=colortex_name, width=size[0], height=size[1])
    img.thug_image_props.compression_type = 'DXT5'
    pixels = [None] * size[0] * size[1]
    for x in range(size[0]):
        for y in range(size[1]):
            r = color[0]
            g = color[1]
            b = color[2]
            a = color[3]
            pixels[(y * size[0]) + x] = [r, g, b, a]
    pixels = [chan for px in pixels for chan in px]
    img.pixels = pixels
    #img.use_fake_user = True
    return img.name

def cleanup_colortex():
    for image in bpy.data.images:
        if image.name.startswith('io_thps_scene_Color_'):
            image.user_clear()
            bpy.data.images.remove(image)
            
def cleanup_mips():
    for image in bpy.data.images:
        if image.name.endswith('_compressed'):
            image.user_clear()
            bpy.data.images.remove(image)

def set_image_compression(matslot, compression):
    if matslot.tex_image:
        matslot.tex_image.thug_image_props.compression_type = compression
        
#----------------------------------------------------------------------------------
def export_tex(filename, directory, target_game, operator=None):
    import time

    def w(fmt, *args):
        outp.write(struct.pack(fmt, *args))

    # denetii - only export images that are from materials with enabled texture slots
    # this should avoid exporting normal/spec map textures used for baking
    #out_materials = bpy.data.materials[:]
    out_materials = []
    for ob in bpy.data.objects:
        if ob.type != 'MESH': continue
        if not hasattr(ob, 'thug_export_scene') or ob.thug_export_scene == False: continue
        for mat in ob.data.materials:
            if not hasattr(mat, 'name') or mat.name in out_materials: continue
            out_materials.append(mat.name)
            
    out_images = []
    out_files = []
    for m_name in out_materials:
        m = bpy.data.materials[m_name]
        if hasattr(m.thug_material_props, 'use_new_mats') and m.thug_material_props.use_new_mats == True \
            and hasattr(m.thug_material_props, 'ugplus_shader') and m.thug_material_props.ugplus_shader != '':
            # Make sure we always export textures which are plugged into the new material/shader system
            # Also need to generate a texture based on a specified color, if no texture was used
            export_textures = []
            if m.thug_material_props.ugplus_shader == 'PBR':
                export_textures.append(m.thug_material_props.ugplus_matslot_normal)
                set_image_compression(m.thug_material_props.ugplus_matslot_normal, 'DXT5')
                export_textures.append(m.thug_material_props.ugplus_matslot_diffuse)
                if m.thug_material_props.ugplus_trans:
                    set_image_compression(m.thug_material_props.ugplus_matslot_diffuse, 'DXT5')
                else:
                    set_image_compression(m.thug_material_props.ugplus_matslot_diffuse, 'DXT1')
                export_textures.append(m.thug_material_props.ugplus_matslot_detail)
                export_textures.append(m.thug_material_props.ugplus_matslot_lightmap)
                export_textures.append(m.thug_material_props.ugplus_matslot_lightmap2)
                export_textures.append(m.thug_material_props.ugplus_matslot_lightmap3)
                export_textures.append(m.thug_material_props.ugplus_matslot_weathermask)
                set_image_compression(m.thug_material_props.ugplus_matslot_weathermask, 'DXT5')
                export_textures.append(m.thug_material_props.ugplus_matslot_snow)
                set_image_compression(m.thug_material_props.ugplus_matslot_snow, 'DXT5')
                
            if m.thug_material_props.ugplus_shader == 'PBR_Lightmapped' or m.thug_material_props.ugplus_shader == 'Glass' or m.thug_material_props.ugplus_shader == 'Diffuse_Lightmapped':
                export_textures.append(m.thug_material_props.ugplus_matslot_normal)
                set_image_compression(m.thug_material_props.ugplus_matslot_normal, 'DXT5')
                export_textures.append(m.thug_material_props.ugplus_matslot_reflection)
                set_image_compression(m.thug_material_props.ugplus_matslot_reflection, 'DXT5')
                export_textures.append(m.thug_material_props.ugplus_matslot_diffuse)
                if m.thug_material_props.ugplus_trans:
                    set_image_compression(m.thug_material_props.ugplus_matslot_diffuse, 'DXT5')
                else:
                    set_image_compression(m.thug_material_props.ugplus_matslot_diffuse, 'DXT1')
                export_textures.append(m.thug_material_props.ugplus_matslot_detail)
                export_textures.append(m.thug_material_props.ugplus_matslot_lightmap)
                set_image_compression(m.thug_material_props.ugplus_matslot_lightmap, 'DXT5')
                export_textures.append(m.thug_material_props.ugplus_matslot_lightmap2)
                set_image_compression(m.thug_material_props.ugplus_matslot_lightmap2, 'DXT5')
                export_textures.append(m.thug_material_props.ugplus_matslot_lightmap3)
                set_image_compression(m.thug_material_props.ugplus_matslot_lightmap3, 'DXT5')
                export_textures.append(m.thug_material_props.ugplus_matslot_lightmap4)
                set_image_compression(m.thug_material_props.ugplus_matslot_lightmap4, 'DXT5')
                export_textures.append(m.thug_material_props.ugplus_matslot_weathermask)
                set_image_compression(m.thug_material_props.ugplus_matslot_weathermask, 'DXT5')
                export_textures.append(m.thug_material_props.ugplus_matslot_snow)
                set_image_compression(m.thug_material_props.ugplus_matslot_snow, 'DXT5')
                export_textures.append(m.thug_material_props.ugplus_matslot_specular)
                set_image_compression(m.thug_material_props.ugplus_matslot_specular, 'DXT5')
                
            elif m.thug_material_props.ugplus_shader == 'PhysicalSky':
                export_textures.append(m.thug_material_props.ugplus_matslot_diffuse_night)
                export_textures.append(m.thug_material_props.ugplus_matslot_detail)
                
            elif m.thug_material_props.ugplus_shader == 'Cloud':
                export_textures.append(m.thug_material_props.ugplus_matslot_cloud)
                set_image_compression(m.thug_material_props.ugplus_matslot_cloud, 'DXT5')
                export_textures.append(m.thug_material_props.ugplus_matslot_detail)
                set_image_compression(m.thug_material_props.ugplus_matslot_detail, 'DXT5')
                export_textures.append(m.thug_material_props.ugplus_matslot_fallback)
                set_image_compression(m.thug_material_props.ugplus_matslot_fallback, 'DXT5')
                
            elif m.thug_material_props.ugplus_shader == 'Grass':
                export_textures.append(m.thug_material_props.ugplus_matslot_diffuse)
                set_image_compression(m.thug_material_props.ugplus_matslot_diffuse, 'DXT5')
                export_textures.append(m.thug_material_props.ugplus_matslot_detail)
                export_textures.append(m.thug_material_props.ugplus_matslot_normal)
                
            elif m.thug_material_props.ugplus_shader == 'Water':
                export_textures.append(m.thug_material_props.ugplus_matslot_fallback)
                set_image_compression(m.thug_material_props.ugplus_matslot_fallback, 'DXT5')
                export_textures.append(m.thug_material_props.ugplus_matslot_reflection)
                
            elif m.thug_material_props.ugplus_shader == 'Water_Custom':
                export_textures.append(m.thug_material_props.ugplus_matslot_normal)
                set_image_compression(m.thug_material_props.ugplus_matslot_normal, 'DXT5')
                export_textures.append(m.thug_material_props.ugplus_matslot_normal2)
                set_image_compression(m.thug_material_props.ugplus_matslot_normal2, 'DXT5')
                export_textures.append(m.thug_material_props.ugplus_matslot_fallback)
                set_image_compression(m.thug_material_props.ugplus_matslot_fallback, 'DXT5')
                export_textures.append(m.thug_material_props.ugplus_matslot_reflection)
                export_textures.append(m.thug_material_props.ugplus_matslot_lightmap)
                set_image_compression(m.thug_material_props.ugplus_matslot_lightmap, 'DXT5')
                export_textures.append(m.thug_material_props.ugplus_matslot_lightmap2)
                set_image_compression(m.thug_material_props.ugplus_matslot_lightmap2, 'DXT5')
                export_textures.append(m.thug_material_props.ugplus_matslot_lightmap3)
                set_image_compression(m.thug_material_props.ugplus_matslot_lightmap3, 'DXT5')
                export_textures.append(m.thug_material_props.ugplus_matslot_lightmap4)
                set_image_compression(m.thug_material_props.ugplus_matslot_lightmap4, 'DXT5')
                export_textures.append(m.thug_material_props.ugplus_matslot_detail)
                
            elif m.thug_material_props.ugplus_shader == 'Ocean':
                export_textures.append(m.thug_material_props.ugplus_matslot_normal)
                set_image_compression(m.thug_material_props.ugplus_matslot_normal, 'DXT5')
                export_textures.append(m.thug_material_props.ugplus_matslot_normal2)
                set_image_compression(m.thug_material_props.ugplus_matslot_normal2, 'DXT5')
                export_textures.append(m.thug_material_props.ugplus_matslot_detail)
                set_image_compression(m.thug_material_props.ugplus_matslot_detail, 'DXT5')
                export_textures.append(m.thug_material_props.ugplus_matslot_fallback)
                
            for tex in export_textures:
                if tex.tex_image == None:
                    if tex.tex_image_name != '':
                        out_images.append(tex.tex_image_name)
                    else:
                        out_images.append(get_colortex(tex.tex_color))
                else:
                    out_images.append(tex.tex_image.name)
                    
        else:
            # denetii - only include texture slots that affect the diffuse color in the Blender material
            passes = [tex_slot.texture for tex_slot in m.th_texture_slots if tex_slot]
            if len(passes) > 4:
                if operator:
                    passes = passes[:4]
            if not passes and m.name != "_THUG_DEFAULT_MATERIAL_":
                if operator:
                    passes = []
            for texture in passes:
                if texture and hasattr(texture, 'image') and texture.image and texture.image.users and texture.image.type in ('IMAGE', 'UV_TEST') and texture.image.source in ('FILE', 'GENERATED') and not texture.image.name in out_images:
                    out_images.append(texture.image.name)
                    
            if m.thug_material_props.grass_props.grassify:
                for i in range(len(m.thug_material_props.grass_props.grass_textures)):
                    if m.thug_material_props.grass_props.grass_textures[i].tex_image_name not in out_images:
                        out_images.append(m.thug_material_props.grass_props.grass_textures[i].tex_image_name)
                    
    output_file = os.path.join(directory, filename)

    _dds_folder = bpy.path.basename(bpy.context.blend_data.filepath)[:-6] # = Name of blend file
    _folder = bpy.path.abspath( "//dds{0}{1}".format( os.sep, _dds_folder ) )

    _folder = bpy.path.native_pathsep(_folder)
    _dds_folder = bpy.path.native_pathsep(_dds_folder)

    os.makedirs( _folder, 0o777, True )

    with open(output_file, "wb") as outp:
        out_files.append( outp )
        exported_images = [img for img in bpy.data.images if img.name in out_images]
        w("2I", 777, 0)

        exported_images_count = 0
        for image in exported_images:
            if image.channels != 4:
                if operator:
                    operator.report({"WARNING"}, "Image \"{}\" has {} channels. Expected 4. Skipping export.".format(image.name, image.channels))
                continue
            LOG.debug("exporting texture: {}".format(image.name))

            # Names formatted as hex are the original checksums from a tex file import, so we should
            # export with the same value for compatibility with CAS items
            if is_hex_string(image.name):
                checksum = int(image.name, 0)
            else:
                checksum = crc_from_string(bytes(image.name, 'ascii'))
            width, height = image.size
            do_compression = (width / 4.0).is_integer() and (height / 4.0).is_integer()
            if do_compression:
                dxt = {
                    "DXT1": 1,
                    "DXT5": 5,
                }[image.thug_image_props.compression_type]
            else:
                dxt = 0
            #LOG.debug("compression: {}".format(dxt))
            mm_offset = 0
            clamp_texture_size = False
            if image.thug_image_props.max_size >= 16:
                clamp_texture_size = True
            elif operator.max_texture_size >= 16:
                if image.name.startswith('LM_'):
                    if operator.max_texture_lightmap_tex == True:
                        clamp_texture_size = True
                else:
                    if operator.max_texture_base_tex == True:
                        clamp_texture_size = True
                        
            if clamp_texture_size == True:
                tex_size = width if width > height else height
                test_size = image.thug_image_props.max_size if image.thug_image_props.max_size >= 16 else operator.max_texture_size
                while True:
                    if tex_size <= test_size:
                        break
                    tex_size /= 2
                    mm_offset += 1
                    
            mipmaps = get_all_compressed_mipmaps(image, dxt, mm_offset, _folder) if do_compression else get_all_mipmaps(image, mm_offset)
            #for idx, (mw, mh, mm) in enumerate(mipmaps):
                #LOG.debug("mm #{}: {}x{} bytes: {}".format(idx, mw, mh, len(mm)))
            if not do_compression:
                mipmaps = [(mw, mh, mm) for mw, mh, mm in mipmaps if mw <= 1024 and mh <= 1024]
                #LOG.debug("after culling: {}".format(len(mipmaps)))
            if not mipmaps:
                continue

            exported_images_count += 1
            width, height, _ = mipmaps[0]
            mipmaps = [mm for mw, mh, mm in mipmaps]
            #LOG.debug("width, height: {}, {}".format(width, height))
            
            mip_levels = min(len(mipmaps), image.thug_image_props.mip_levels)
            if mip_levels == 0:
                mip_levels = len(mipmaps)
                
            texel_depth = 32
            palette_depth = 0
            palette_size = 0

            channels = image.channels
            assert channels == 4

            w("I", checksum)
            w("I", width)
            w("I", height)
            w("I", mip_levels)
            w("I", texel_depth)
            w("I", palette_depth)
            w("I", dxt)
            w("I", palette_size)

            for mip in range(0, mip_levels):
                mipmap = mipmaps[mip]
                w("I", len(mipmap))
                pixels = mipmap # image.pixels[:]
                if dxt != 0:
                    for i in range(0, len(pixels), 2**16):
                        sub_pixels = pixels[i:i + 2**16]
                        w(str(len(sub_pixels)) + "B", *sub_pixels)
                    continue

                out_pixels = []
                _append = out_pixels.append

                for i in range(0, len(pixels), 4):
                    j = i # i * channels
                    """
                    r = int(pixels[j] * 255) & 0xff
                    g = int(pixels[j + 1] * 255) & 0xff
                    b = int(pixels[j + 2] * 255) & 0xff
                    a = (int(pixels[j + 3] / 2.0 * 255.0) & 0xff) if channels == 4 else 255
                    """
                    r = int(pixels[j]) & 0xff
                    g = int(pixels[j + 1]) & 0xff
                    b = int(pixels[j + 2]) & 0xff
                    a = (int(pixels[j + 3] / 2.0) & 0xff)
                    _append(a << 24 | r << 16 | g << 8 | b)
                if False and target_game != "THUG2":
                    swizzled = swizzle(out_pixels, width, height, 8, 0, False)
                    w(str(len(swizzled)) + "I", *swizzled)
                else:
                    w(str(len(out_pixels)) + "I", *out_pixels)
            del mipmaps[:]

        outp.seek(4)
        w("I", exported_images_count)

    # Remove temp solid-color images generated during export
    cleanup_colortex()

    cleanup_mips()

# OPERATORS
#############################################
class THUG2TexToImages(bpy.types.Operator):
    bl_idname = "io.thug2_tex"
    bl_label = "THPS Xbox/PC .tex"
    # bl_options = {'REGISTER', 'UNDO'}

    filename: StringProperty(name="File Name")
    directory: StringProperty(name="Directory")

    def execute(self, context):
        filename = self.filename
        directory = self.directory

        import os

        p = Printer()
        p("Reading .TEX file: {}", os.path.join(directory, filename))
        with open(os.path.join(directory, filename), "rb") as inp:
            r = Reader(inp.read())
            read_tex(r, p)

        return {'FINISHED'}

    def invoke(self, context, event):
        wm = bpy.context.window_manager
        wm.fileselect_add(self)

        return {'RUNNING_MODAL'}
        
        
from bpy_extras.io_utils import ImportHelper

class THUGImgToImages(bpy.types.Operator, ImportHelper):
    bl_idname = "io.thug_img"
    bl_label = "THPS/THUG .img"
    bl_options = {'PRESET', 'UNDO'}
    filename_ext = ".img"

    filter_glob: StringProperty(default="*.img;*.img.xbx;*img.dat", options={"HIDDEN"})
    filename: StringProperty(name="File Name")
    directory: StringProperty(name="Directory")

    # Selected files
    files: CollectionProperty(type=bpy.types.PropertyGroup)
    
    def execute(self, context):
        filename = self.filename
        directory = self.directory
        
        # iterate through the selected files
        for i in self.files:
            import_img(os.path.join(directory, i.name), i.name)
        
            #import_img(os.path.join(directory, filename), filename)

        return {'FINISHED'}

    def invoke(self, context, event):
        wm = bpy.context.window_manager
        wm.fileselect_add(self)

        return {'RUNNING_MODAL'}

