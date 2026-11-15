"""Render exact animation states. Identical held frames reuse identical pixels.
State hashes include shutter endpoints, geometry transforms, visibility, lights,
and animated shader inputs. No interpolation or AI frame generation is used.
"""
import bpy,sys,json,hashlib,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source_sha=hashlib.sha256((ROOT/'Mines3D_DeepSector.blend').read_bytes()).hexdigest()
renderer_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
cachefile=ROOT/'render_cache.json'
cache=json.loads(cachefile.read_text()) if cachefile.exists() else {}
if cache.get('source_sha')!=source_sha or cache.get('renderer_sha')!=renderer_sha:
    cache={'source_sha':source_sha,'renderer_sha':renderer_sha,'frames':{}}
(ROOT/'render_complete.json').write_text(json.dumps({'finished':False,'source_sha':source_sha,'renderer_sha':renderer_sha}),encoding='utf8')
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Mines3D_DeepSector.blend'),load_ui=False)
s=bpy.context.scene
s.render.engine='CYCLES';s.render.resolution_x=1080;s.render.resolution_y=1920;s.render.resolution_percentage=100
s.cycles.samples=256;s.cycles.adaptive_threshold=.005;s.cycles.use_adaptive_sampling=True
s.cycles.use_denoising=True;s.cycles.denoiser='OPENIMAGEDENOISE';s.cycles.denoising_input_passes='RGB_ALBEDO_NORMAL'
if hasattr(s.cycles,'denoising_quality'):s.cycles.denoising_quality='HIGH'
s.cycles.device='GPU';s.render.use_persistent_data=True;s.render.use_sequencer=False
s.render.image_settings.file_format='PNG';s.render.image_settings.color_depth='16';s.render.image_settings.color_mode='RGBA'
p=bpy.context.preferences.addons['cycles'].preferences;p.compute_device_type='CUDA';p.get_devices()
for d in p.devices:d.use=d.type=='CUDA'
assert any(d.use and d.type=='CUDA' for d in p.devices)
objects=sorted(s.objects,key=lambda o:o.name)
animated_materials=[m for m in bpy.data.materials if m.use_nodes and m.node_tree.animation_data]
def state(t):
    f=int(t);s.frame_set(max(1,f),subframe=max(0,t-f))
    vals=[]
    for o in objects:
        vals.extend((o.name,o.hide_render))
        if not o.hide_render:
            vals.extend(round(v,7) for row in o.matrix_world for v in row)
            if o.type=='LIGHT':vals.append(round(o.data.energy,6))
    for m in animated_materials:
        for n in m.node_tree.nodes:
            for inp in n.inputs:
                if hasattr(inp,'default_value'):
                    v=inp.default_value
                    if isinstance(v,(float,int)):vals.append(round(float(v),7))
    return vals
seen={};mapping={}
for f in range(1,577):
    signature=hashlib.sha256(repr([state(f-.175),state(f),state(f+.175)]).encode()).hexdigest()
    mapping[f]=seen.setdefault(signature,f)
(ROOT/'frame_map.json').write_text(json.dumps(mapping,indent=2),encoding='utf8')
priority=[337,350,370,197]
frames=sorted(set(mapping.values()),key=lambda f:(0,priority.index(f)) if f in priority else (1,f))
print('RENDER_PLAN',json.dumps({'frames':576,'unique_exact_states':len(frames),'engine':s.render.engine,'resolution':[1080,1920],'samples':256,'adaptive_threshold':.005,'backend':'CUDA','motion_blur':s.render.motion_blur_shutter,'device':[d.name for d in p.devices if d.use]}),flush=True)
start=time.time()
for idx,f in enumerate(frames):
    dest=ROOT/'renders'/('%04d.png'%f)
    if dest.exists() and cache['frames'].get(str(f))==hashlib.sha256(dest.read_bytes()).hexdigest():
        print('FRAME_EXISTS',f,flush=True);continue
    s.frame_set(f);s.render.filepath=str(dest);then=time.time();bpy.ops.render.render(write_still=True)
    print('FRAME_DONE',json.dumps({'frame':f,'unique_index':idx+1,'unique_total':len(frames),'seconds':round(time.time()-then,2),'elapsed':round(time.time()-start,2)}),flush=True)
    cache['frames'][str(f)]=hashlib.sha256(dest.read_bytes()).hexdigest()
    cachefile.write_text(json.dumps(cache,indent=2),encoding='utf8')
    (ROOT/'render_progress.json').write_text(json.dumps({'frame':f,'completed_unique':idx+1,'total_unique':len(frames),'elapsed_seconds':time.time()-start}),encoding='utf8')
(ROOT/'render_complete.json').write_text(json.dumps({'finished':True,'source_sha':source_sha,'renderer_sha':renderer_sha,'frames':576,'unique_frames':len(frames),'seconds':time.time()-start}),encoding='utf8')
print('RENDER_COMPLETE',flush=True)
