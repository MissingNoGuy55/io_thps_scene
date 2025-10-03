# io_thps_scene (Blender 4.5 fork)
This fork of io_thps_scene aims to bring the addon to a modern Blender version, specifically 4.5.3 and beyond.

This Blender addon allows you to export a scene as a custom level for some of the classic THPS games. Also includes a variety of import tools to load existing levels/assets, as well as a fully integrated lightmap baking tool.

## Why a fork?

Denetii was updating the addon to integrate with Blender 2.8. However, development seems to have stalled, or ceased, years ago. The addon has not been updated in years. In that time, Blender has gone beyond Blender 2, all the way to Blender 4. Simply put, I was tired of waiting and took matters into my own hands. I was exhausted with using Blender 2.79b, which suffers from a multitude of issues both performance and functionality-wise. I also wanted to... be able to edit more than one object without having to use the buggy MultiEdit addon, along with having GPU-accelerated lightmap baking, which did not work with Blender 2.79b (I have an RTX 2070).

## New things

You may notice the presence of a new utility in the `assets` folder, named `dxtcompressor`. This is a utility written in C by me that basically does what the old addon did and processes bytes exported by the addon to convert into a DXT image for export to THPS. It also caches the result, compares it to the input, and will reuse it if it matches. It was necessary to develop a tool like this because the old Blender OpenGL API no longer works.

Do note however that depending on how many textures your level uses, the cache can range anywhere from megabytes to several gigabytes. These files do not have to be shared when sharing an exported level.

## What does not work still

Currently, lightmap groups and the visualization of surface flags do not work. The former will be easier to fix, but the latter will be difficult. Surface flag visualization does not work because the code that displayed surface flags was reliant on the old BGL API (Blender OpenGL), which became inaccessible at the time the Blender developers began to add Vulkan functionality.

## Examples 
Denetii host a selection of custom levels built with the old addon on the Tony Hawk Archive: http://tharchive.net/misc/custom_levels.html
You can also find a larger collection of custom levels at THPSX: http://thpsx.com/community-upload-list/
