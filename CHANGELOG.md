# 7 October 2025

## Lightmap group fixes
* Unbaking a lightmap group will no longer remove the objects from it.
* Lightmap group UV generation now uses a margin of `(16384 / ( img_res * ( img_res / 4 ) ) )`, which scales with image size.
* When creating lightmap group UVs, the active UV layer will stay what it was set to prior.
* Objects with `hide_render` set to true or with no materials can no longer be added to lightmap groups.
** This is because Blender would throw an exception when attempting to bake these.
* Lightmap groups are prioritized over standard objects when the baking process begins.
* Lightmap groups now bake what is selected, rather than one at a time.
** Baking multiple lightmap groups now works as intended.
** This is the only way `bpy.ops.object.bake` can bake to a single texture with multiple objects. It is destructive, and it will wipe previously-baked data if you select and bake different objects in the group. Be careful!
* Fixed a serious bug where deleting lightmap groups would not update IDs in objects in the groups that come after the deleted group.

## Baking/unbaking fixes
* Lightmap unbaking is now threaded, resulting in the unbake process being significantly faster.
** Lightmap baking cannot be threaded due to `bpy.ops.object.bake` not being thread-safe. Trust me, I tried.

## Texture export fixes
* `dxtcompressor` now caches properly. It was not working correctly prior.
* GLEW is no longer required to build or run `dxtcompressor` on Windows.

# 3 October 2025

* Fixed autosplit entirely.
* Fixed autosplit not exporting lightmap UVs correctly.
* Fixed destructive triangulation when exporting levels.
* Fixed bulk unbaking wiping materials off the last object that is baked.
* Added `dxtcompressor` utility and restored texture exporting.
* Fixed bug where hiding a rail object would throw a Python exception.
* Fixed bug where bulk lightmap baking would attempt to bake an object not set to appear in renders.
