"""Apply selected-cell height response to the existing scene, without rebuilding assets."""
import bpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
assert bpy.app.background
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Mines3D_DeepSector.blend'),load_ui=False)
bpy.context.preferences.filepaths.save_version=0
for o in bpy.context.scene.objects:
    if o.name.startswith('Selected safe cell'):
        o.location.z=.45;o.keyframe_insert('location',frame=192)
        o.location.z=.15;o.keyframe_insert('location',frame=196)
for screen in bpy.data.screens:
    for a in screen.areas:
        if a.type=='VIEW_3D':
            a.spaces.active.region_3d.view_perspective='CAMERA'
            a.spaces.active.shading.type='MATERIAL'
            a.spaces.active.shading.use_scene_world=True
            a.spaces.active.shading.use_scene_lights=True
            a.spaces.active.overlay.show_overlays=False
bpy.context.scene.frame_set(220)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Mines3D_DeepSector.blend'))
print('Selection outline follows opened cell height; camera material preview configured.')
