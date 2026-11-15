"""Render selected frames with explicit settings, retaining lossless 16-bit PNGs."""
import bpy,sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
mode=args[0] if args else 'preview'
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Mines3D_DeepSector.blend'))
s=bpy.context.scene
s.render.engine='CYCLES';s.render.use_sequencer=False
s.render.resolution_x=1080;s.render.resolution_y=1920
s.render.resolution_percentage=50 if mode=='preview' else 100
s.cycles.samples=48 if mode=='preview' else 256
s.cycles.adaptive_threshold=.025 if mode=='preview' else .005
s.render.image_settings.file_format='PNG';s.render.image_settings.color_depth='16';s.render.image_settings.color_mode='RGBA'
p=bpy.context.preferences.addons['cycles'].preferences;p.compute_device_type='CUDA';p.get_devices()
for d in p.devices:d.use=d.type=='CUDA'
s.cycles.device='GPU';s.render.use_persistent_data=True
print('ACTUAL_SETTINGS',json.dumps({'engine':s.render.engine,'percentage':s.render.resolution_percentage,'samples':s.cycles.samples,'adaptive_threshold':s.cycles.adaptive_threshold,'devices':[(d.name,d.type,d.use) for d in p.devices]}),flush=True)
frames=list(map(int,args[1:])) if len(args)>1 else [60,220,340,360,400,490]
for f in frames:
    dest=ROOT/('review' if mode=='preview' else 'renders')/('%04d.png'%f)
    if mode!='preview' and dest.exists():continue
    s.frame_set(f);s.render.filepath=str(dest);start=time.time();bpy.ops.render.render(write_still=True)
    print('FRAME_DONE',f,round(time.time()-start,2),str(dest),flush=True)
