"""Bake the approved animated mineral volume, isolated from the editable source.
16 RGBA frames, orthographic camera at the game's default angle; never saves blend.
"""
import bpy, math, json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'mobile/dust';OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Mines3D_DeepSector.blend'))
s=bpy.context.scene;s.render.engine='CYCLES';s.render.use_sequencer=False
s.render.resolution_x=256;s.render.resolution_y=256;s.render.resolution_percentage=100
s.render.film_transparent=True;s.render.image_settings.file_format='PNG'
s.render.image_settings.color_mode='RGBA';s.render.image_settings.color_depth='8'
s.cycles.samples=48;s.cycles.adaptive_threshold=.02
p=bpy.context.preferences.addons['cycles'].preferences;p.compute_device_type='CUDA';p.get_devices()
for d in p.devices:d.use=d.type=='CUDA'
s.cycles.device='GPU';s.render.use_persistent_data=True
cam=bpy.data.objects.new('Mobile dust bake camera',bpy.data.cameras.new('Mobile dust bake camera'))
s.collection.objects.link(cam);cam.data.type='ORTHO';cam.data.ortho_scale=5.5
target=Vector((2,-1,1.2));yaw=math.radians(36);pitch=math.radians(43)
cam.location=target+Vector((math.sin(yaw)*math.cos(pitch),-math.cos(yaw)*math.cos(pitch),math.sin(pitch)))*12
cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();s.camera=cam
names=[o.name for o in bpy.data.objects if 'dust' in o.name.lower() and o.type=='MESH']
assert names, 'No source dust objects'
print('DUST_OBJECTS',names,flush=True)
for i in range(16):
    frame=337+round(i*144/15);s.frame_set(frame)
    for o in bpy.data.objects:
        if o.type in {'MESH','FONT','CURVE','VOLUME'}:
            o.hide_render=o.name not in names
            o.keyframe_insert(data_path='hide_render',frame=frame)
    s.render.filepath=str(OUT/('%02d.png'%i));bpy.ops.render.render(write_still=True)
    print('DUST_FRAME',i,frame,flush=True)
(OUT/'contract.json').write_text(json.dumps({'frames':16,'duration':6,'columns':4,'rows':4,'world_size':5.5,'center_above_cell':1.2,'source':'Mines3D_DeepSector.blend','frame_start':337,'frame_end':481},indent=2))
