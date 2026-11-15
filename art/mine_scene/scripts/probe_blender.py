import bpy, json
print('BLENDER_VERSION', bpy.app.version_string)
print('INITIAL_FILE', bpy.data.filepath)
print('RENDER_ENUM', [x.identifier for x in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items])
prefs=bpy.context.preferences.addons.get('cycles')
if prefs:
    try:
        prefs.preferences.compute_device_type='CUDA'
        prefs.preferences.get_devices()
        print('CYCLES_DEVICES', [(d.name,d.type) for d in prefs.preferences.devices])
    except Exception as exc: print('CYCLES_ERROR',str(exc))
print('AUDIO_STRIPS',hasattr(bpy.types.SequenceEditor,'strips'))
print('SCENE_SETTINGS', [p.identifier for p in bpy.types.RenderSettings.bl_rna.properties if 'motion' in p.identifier])
