"""Read-only asset and timeline checks; no renderer or Android claim."""
import bpy,json,math
from pathlib import Path
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
ROOT=Path(__file__).resolve().parents[1]
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Mines3D_DeepSector.blend'),load_ui=False)
s=bpy.context.scene
assert (s.render.resolution_x,s.render.resolution_y,s.render.fps,s.frame_end)==(1080,1920,24,576)
assert len(s.timeline_markers)==10
states={}
for f in [1,115,146,169,193,251,313,337,344,482,576]:
    s.frame_set(f)
    visible=[o for o in s.objects if not o.hide_render]
    states[f]={'visible_objects':len(visible),'upper_visible':sum(not o.hide_render for o in bpy.data.collections['04_Upper_board'].objects),'fragments_visible':sum(not o.hide_render for o in bpy.data.collections['07_Blast_fragments'].objects),'blast_light_watts':bpy.data.lights['Blast light at actual cell'].energy}
assert states[115]['upper_visible']>100 and states[146]['upper_visible']==0
assert states[313]['blast_light_watts']==0 and states[337]['blast_light_watts']>3000 and states[482]['blast_light_watts']==0
s.frame_set(220);coords=[]
assert all(abs(o.location.z-.15)<1e-5 for o in s.objects if o.name.startswith('Selected safe cell'))
for j in range(5):
    for i in range(5):
        v=world_to_camera_view(s,s.camera,Vector((i-2,j-2,.44)))
        assert .03<v.x<.97 and .19<v.y<.82,(i,j,tuple(v))
        coords.append({'cell':[i,j,0],'screen_px':[round(v.x*1080,1),round((1-v.y)*1920,1)]})
sounds=[{'name':x.name,'packed':bool(x.packed_file),'path':x.filepath} for x in bpy.data.sounds]
assert len(sounds)==6 and all(x['packed'] for x in sounds)
assert all(im.packed_file for im in bpy.data.images if im.source=='FILE')
contract=json.loads((ROOT/'scene_contract.json').read_text());assert contract['safe_open_clue']==2
trajectory=json.loads((ROOT/'fragment_trajectories.json').read_text());collisions=trajectory['collisions']
steelhits=[x for x in collisions if x[2]=='steel support'];assert len(steelhits)>0
s.frame_set(490);contact_checks=[]
open_cells={(0,0),(0,1),(0,2),(1,1),(1,2),(2,0),(3,0),(3,1),(4,0),(2,1)}
for o in bpy.data.collections['07_Blast_fragments'].objects:
    if not o.name.startswith('Ballistic fragment'):continue
    x,y,z=o.location;i=round(x+2);j=round(y+2)
    if 0<=i<5 and 0<=j<5 and abs(x-(i-2))<.33 and abs(y-(j-2))<.33 and (i,j)!=(4,1):
        surface=.1175 if (i,j) in open_cells else .427
        bottom=min((o.matrix_world @ v.co).z for v in o.data.vertices)
        gap=bottom-surface
        assert -.025<gap<.025,(o.name,i,j,gap)
        contact_checks.append({'fragment':o.name,'cell':[i,j,0],'bottom_gap_metres':gap})
assert contact_checks
result={'status':'PASS','scope':'Blender source / geometry framing / animation timing / packed dependencies; no Android tests','states':states,'active_cell_centres':coords,'packed_audio':sounds,'steel_collision_events':steelhits,'objects':len(s.objects),'fonts':[x.name for x in bpy.data.fonts],'first_safe_clue':2}
result['settled_fragment_surface_checks']=contact_checks
(ROOT/'review/scene-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'status':'PASS','objects':len(s.objects),'cell_centres_in_safe_frame':len(coords),'packed_sound_stems':len(sounds),'steel_collision_events':len(steelhits)},ensure_ascii=False))
