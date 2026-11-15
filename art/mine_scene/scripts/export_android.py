"""Export the approved Blender art to the existing GLES2 renderer.
Reads the source blend in an isolated process; never saves or backs up the blend.
M3D2 stores named triangle templates: position, normal, linear RGB, material kind.
The original geometry is retained; rock LOD uses 28% of the source triangles.
"""
import bpy, struct, json, hashlib, math
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parents[1]/'app/src/main/assets/mine'
OUT.mkdir(parents=True,exist_ok=True)
assert bpy.app.background
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Mines3D_DeepSector.blend'))
s=bpy.context.scene
s.frame_set(1)
groups={}
def kind(mat):
    n=mat.name if mat else ''
    if n.startswith('ROCK'):return 1
    if n.startswith('STEEL'):return 2
    if 'lamp glass' in n or 'embers' in n or 'hot core' in n:return 3
    if 'Readable ink' in n:return 4
    return 0
def rgb(mat):
    if mat and mat.use_nodes:
        bs=next((n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
        if bs:
            if kind(mat)==3 and 'Emission Color' in bs.inputs:return tuple(bs.inputs['Emission Color'].default_value[:3])
            return tuple(bs.inputs['Base Color'].default_value[:3])
    return (.1,.15,.18)
def emit(name,objects,origin=(0,0,0),lod=False,bevel_lod=False):
    data=[];origin=Vector(origin)
    for o in objects:
        if o.type not in {'MESH','CURVE','FONT'}:continue
        if name=='environment' and o.name.startswith('Lamp housing'):
            # The source uses a solid housing cylinder. Expose the original emissive
            # glass in GLES rather than letting the opaque housing conceal it.
            o.scale.x*=.60;o.scale.y*=.60
        if bevel_lod:
            for mod in o.modifiers:
                if mod.type=='BEVEL':mod.segments=1
        if lod and o.type=='MESH' and ('Basalt' in o.name or 'Footfall' in o.name):
            mod=o.modifiers.new('Mobile rock LOD','DECIMATE');mod.ratio=.28
        ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
        if not me:continue
        me.calc_loop_triangles();normal_matrix=ev.matrix_world.to_3x3().inverted().transposed()
        for tri in me.loop_triangles:
            mat=me.materials[tri.material_index] if len(me.materials) else None
            col=rgb(mat);k=kind(mat)
            for li in tri.loops:
                v=me.vertices[me.loops[li].vertex_index]
                p=ev.matrix_world@v.co-origin
                n=normal_matrix@me.corner_normals[li].vector;n.normalize()
                data.extend((p.x,p.z,-p.y,n.x,n.z,-n.y,*col,float(k)))
        ev.to_mesh_clear()
    groups[name]=data
    print(name,len(data)//30,'triangles',flush=True)

env=[]
for c in ['01_Rock_cutaway','02_Steel_structure','05_Practical_lights']:
    env.extend(o for o in bpy.data.collections[c].objects if o.type!='LIGHT')
emit('environment',env,lod=True)
upper=bpy.data.collections['04_Upper_board'].objects
emit('support',[o for o in upper if o.name.startswith(('Layer crossbeam','Layer sidebeam','Underslung joist','Deck fixing','Safety stripe'))],(0,0,1.5))
lower=bpy.data.collections['03_Lower_board'].objects
def at(x,y):
    return [o for o in lower if o.type=='MESH' and abs(o.location.x-x)<.46 and abs(o.location.y-y)<.46 and o.location.z<.45 and not o.name.startswith('Flag')]
emit('closed',at(0,-1),(0,-1,0))
emit('opened',at(-2,-2),(-2,-2,0))
emit('closed_lod',at(0,-1),(0,-1,0),bevel_lod=True)
emit('opened_lod',at(-2,-2),(-2,-2,0),bevel_lod=True)
s.frame_set(251)
emit('flag',[o for o in lower if o.name.startswith(('Flag base','Flag mast','Amber flag cloth'))],(-1,-2,0))
s.frame_set(576)
emit('damaged',[o for o in bpy.data.objects if o.name.startswith(('Charred impact cavity','Broken rim','Residual ember'))],(2,-1,0))
s.frame_set(337)
for index in [0,16,25]:
    ob=bpy.data.objects['Ballistic fragment %02d'%index]
    emit('fragment'+str(index),[ob],tuple(ob.location))
s.frame_set(338)
emit('ignition',[bpy.data.objects['Short luminous ignition']],(2,-1,.52))
ink=bpy.data.materials['Readable ink'];font=bpy.data.fonts.get('Noto Sans Bold')
for digit in range(1,7):
    cu=bpy.data.curves.new('Mobile digit '+str(digit),'FONT');cu.body=str(digit);cu.font=font
    cu.align_x='CENTER';cu.align_y='CENTER';cu.size=.52;cu.extrude=0;cu.bevel_depth=0;cu.resolution_u=5;cu.materials.append(ink)
    ob=bpy.data.objects.new(cu.name,cu);s.collection.objects.link(ob)
    bpy.context.view_layer.update();emit('digit'+str(digit),[ob])
path=OUT/'scene.m3d'
with path.open('wb') as f:
    f.write(b'M3D2');f.write(struct.pack('>i',len(groups)))
    for name,values in groups.items():
        b=name.encode();f.write(struct.pack('>i',len(b)));f.write(b)
        f.write(struct.pack('>i',len(values)//10));f.write(struct.pack('>'+str(len(values))+'f',*values))
report={'source_sha256':hashlib.sha256((ROOT/'Mines3D_DeepSector.blend').read_bytes()).hexdigest(),
        'export_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'format':'M3D2 / position normal linearRGB material',
        'axis':'Android (x,y,z) = Blender (x,z,-y)','triangles':{k:len(v)//30 for k,v in groups.items()},
        'material_note':'Same source geometry and original maps; GLES2 directional/point lighting replaces Cycles. No offline framebuffer in the playable scene.'}
(ROOT/'mobile-export.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print('EXPORT_COMPLETE',path,flush=True)
