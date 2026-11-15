"""Mines3D / Deep Sector — editable Blender visual target, phase 1 only.
Runs in a fresh background process. Does not open or overwrite a user's Blender session.
Cell pitch 1m; tile .91m; layer spacing 1.5m; camera yaw36/pitch43/FOV40.
All fracture and dust trajectories are authored here, deterministic and scrubbable.
"""
import bpy, math, random, json, sys
from pathlib import Path
from mathutils import Vector, Euler, noise

ROOT=Path(__file__).resolve().parents[1]
R=random.Random(20261112); FPS=24; HIT=337
assert bpy.app.background, 'Run in a new background Blender process; preserve any open user scene.'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.preferences.filepaths.save_version=0  # no automatic backup files
s=bpy.context.scene
s.render.engine='CYCLES'
s.cycles.samples=256;s.cycles.use_adaptive_sampling=True;s.cycles.adaptive_threshold=.005
s.cycles.use_denoising=True;s.cycles.denoiser='OPENIMAGEDENOISE'
s.cycles.denoising_input_passes='RGB_ALBEDO_NORMAL'
if hasattr(s.cycles,'denoising_quality'):s.cycles.denoising_quality='HIGH'
s.cycles.max_bounces=12;s.cycles.transparent_max_bounces=16;s.cycles.volume_bounces=2
s.cycles.seed=43;s.cycles.use_animated_seed=False
s.render.use_persistent_data=True
prefs=bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type='CUDA';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='CUDA'
s.cycles.device='GPU'
s.render.resolution_x=1080;s.render.resolution_y=1920;s.render.resolution_percentage=100
s.render.fps=FPS;s.frame_start=1;s.frame_end=576
s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGBA';s.render.image_settings.color_depth='16'
s.render.use_motion_blur=True;s.render.motion_blur_shutter=.35
s.view_settings.view_transform='AgX'
try:s.view_settings.look='AgX - Medium High Contrast'
except TypeError:pass
s.view_settings.exposure=.15
s.render.film_transparent=False
world=bpy.data.worlds.new('Deep blue mine atmosphere');world.use_nodes=True
bg=next(n for n in world.node_tree.nodes if n.type=='BACKGROUND');bg.inputs['Color'].default_value=(.065,.10,.16,1);bg.inputs['Strength'].default_value=.18;s.world=world
s.unit_settings.system='METRIC'

def collection(name):
    c=bpy.data.collections.new(name);s.collection.children.link(c);return c
COL={name:collection(name) for name in ['01_Rock_cutaway','02_Steel_structure','03_Lower_board','04_Upper_board','05_Practical_lights','06_Selection','07_Blast_fragments','08_Dust_and_flash','09_Cameras','10_Soundtrack']}
def put(o,key):
    for c in list(o.users_collection):c.objects.unlink(o)
    COL[key].objects.link(o);return o
def material(name,color,metallic=0,rough=.6,emission=0):
    m=bpy.data.materials.new(name);m.use_nodes=True
    p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    p.inputs['Base Color'].default_value=(*color,1);p.inputs['Metallic'].default_value=metallic;p.inputs['Roughness'].default_value=rough
    p.inputs['Emission Color'].default_value=(*color,1);p.inputs['Emission Strength'].default_value=emission
    return m
def textured(name,base,rough,metallic=0):
    m=material(name,(.2,.2,.2),metallic);nt=m.node_tree;p=next(n for n in nt.nodes if n.type=='BSDF_PRINCIPLED')
    for file,inp,iscolor in [(base,'Base Color',True),(rough,'Roughness',False)]:
        tex=nt.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(ROOT/'textures'/file),check_existing=True);tex.projection='BOX';tex.projection_blend=.28
        if not iscolor:tex.image.colorspace_settings.name='Non-Color'
        nt.links.new(tex.outputs['Color'],p.inputs[inp])
    return m
rock=textured('ROCK · layered basalt', 'rock_basecolor.png','rock_roughness.png')
nt=rock.node_tree;p=next(n for n in nt.nodes if n.type=='BSDF_PRINCIPLED')
tex=nt.nodes.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=27;tex.inputs['Detail'].default_value=4
bump=nt.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.6;bump.inputs['Distance'].default_value=.07;nt.links.new(tex.outputs['Fac'],bump.inputs['Height']);nt.links.new(bump.outputs['Normal'],p.inputs['Normal'])
steel=textured('STEEL · worn blue enamel','steel_basecolor.png','steel_roughness.png',.65)
edge=material('Exposed steel edges',(.29,.34,.36),.82,.34)
dark=material('Recess / shadow gasket',(.012,.021,.027),.15,.7)
tile=material('Closed mineral plate',(.035,.071,.090),.30,.61)
ochre=material('Warm safety paint',(.73,.36,.055),.18,.5)
openmat=material('Opened ceramic enamel',(.42,.59,.58),.16,.48)
clue=material('Readable ink',(.008,.058,.076),.15,.55)
teal=material('Selection / pale cyan',(.10,.85,.87),.3,.3,2)
gold=material('Amber fabric',(.95,.42,.045),0,.84)
lampmat=material('Warm miner lamp glass',(1,.42,.09),.05,.26,8)
black=material('Blast char',(.015,.011,.008),.1,.98)
char=material('Fractured aggregate',(.13,.14,.135),.1,.9)
ember=material('Cooling embers',(.9,.12,.013),.15,.5,2)

def cube(name,loc,dim,mat,group='02_Steel_structure',bevel=.025):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=dim
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if mat:o.data.materials.append(mat)
    if bevel:
        m=o.modifiers.new('Small machined edge','BEVEL');m.width=bevel;m.segments=3
        m=o.modifiers.new('Weighted corner normals','WEIGHTED_NORMAL')
    return put(o,group)
def cylinder(name,loc,radius,depth,mat,group='02_Steel_structure',vertices=16):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=depth,location=loc);o=bpy.context.object;o.name=name;o.data.materials.append(mat)
    mod=o.modifiers.new('Rim bevel','BEVEL');mod.width=min(.012,depth*.18);mod.segments=2
    o.modifiers.new('Weighted normals','WEIGHTED_NORMAL');return put(o,group)
def line(name,points,radius,mat,group='02_Steel_structure'):
    cu=bpy.data.curves.new(name,'CURVE');cu.dimensions='3D';cu.resolution_u=12;cu.bevel_depth=radius;cu.bevel_resolution=3
    sp=cu.splines.new('POLY');sp.points.add(len(points)-1)
    for p,co in zip(sp.points,points):p.co=(*co,1)
    o=bpy.data.objects.new(name,cu);COL[group].objects.link(o);o.data.materials.append(mat);return o
def beam(name,a,b,width,mat=steel):
    a=Vector(a);b=Vector(b);o=cube(name,(a+b)/2,(width,width,(b-a).length),mat)
    o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler();return o
def point(name,loc,color,power,size=.3):
    d=bpy.data.lights.new(name,'POINT');d.energy=power;d.color=color;d.shadow_soft_size=size
    o=bpy.data.objects.new(name,d);o.location=loc;COL['05_Practical_lights'].objects.link(o);return o
def area(name,loc,target,color,power,size):
    d=bpy.data.lights.new(name,'AREA');d.energy=power;d.color=color;d.shape='DISK';d.size=size
    o=bpy.data.objects.new(name,d);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();COL['05_Practical_lights'].objects.link(o);return o
def rockmesh(name,loc,scale,seed,group='01_Rock_cutaway',sub=2):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=sub,radius=1,location=loc);o=bpy.context.object;o.name=name
    for v in o.data.vertices:
        n=noise.noise_vector(v.co*2.9+Vector((seed,seed*.3,seed*.7)))
        v.co*=1+n.x*.19;v.co.z+=n.z*.1
    o.scale=scale;o.data.materials.append(rock if group=='01_Rock_cutaway' else char)
    return put(o,group)
font=bpy.data.fonts.load(str(ROOT/'fonts/NotoSans-Bold.ttf'))
def text_obj(name,body,loc,size,mat,group='03_Lower_board',rot=(0,0,0)):
    d=bpy.data.curves.new(name,'FONT');d.body=body;d.font=font;d.align_x='CENTER';d.align_y='CENTER';d.size=size;d.extrude=.001;d.bevel_depth=.0006
    o=bpy.data.objects.new(name,d);o.location=loc;o.rotation_euler=rot;d.materials.append(mat);COL[group].objects.link(o);return o
def hide_before(o,f):
    o.hide_render=True;o.keyframe_insert('hide_render',frame=1);o.keyframe_insert('hide_render',frame=f-1)
    o.hide_render=False;o.keyframe_insert('hide_render',frame=f)
    o.hide_viewport=True;o.keyframe_insert('hide_viewport',frame=1);o.keyframe_insert('hide_viewport',frame=f-1)
    o.hide_viewport=False;o.keyframe_insert('hide_viewport',frame=f)
def hide_at(o,f):
    o.hide_render=False;o.keyframe_insert('hide_render',frame=1);o.keyframe_insert('hide_render',frame=f-1)
    o.hide_render=True;o.keyframe_insert('hide_render',frame=f)
    o.hide_viewport=False;o.keyframe_insert('hide_viewport',frame=1);o.keyframe_insert('hide_viewport',frame=f-1)
    o.hide_viewport=True;o.keyframe_insert('hide_viewport',frame=f)
def key(o,path,f):o.keyframe_insert(path,frame=f)

# Asymmetrical geological cutaway; foreground is unobstructed for touch targets.
cube('Floating geological foundation',(0,0,-.84),(6.35,6.18,.95),rock,'01_Rock_cutaway',.23)
for i in range(42):
    if i<21:
        loc=(-3.15+R.uniform(-.16,.16),R.uniform(-2.8,3.0),R.uniform(-.9,1.8));sc=(R.uniform(.35,.7),R.uniform(.45,.8),R.uniform(.45,.8))
    else:
        loc=(R.uniform(-2.8,2.7),3.05+R.uniform(-.1,.18),R.uniform(-.8,2.8));sc=(R.uniform(.4,.85),R.uniform(.38,.66),R.uniform(.5,1.0))
    rockmesh('Basalt fractured outcrop %02d'%i,loc,sc,i*.31,sub=3)
for i in range(38):
    a=R.uniform(0,math.tau);r=R.uniform(2.9,3.7)
    rockmesh('Footfall scree %02d'%i,(math.cos(a)*r,math.sin(a)*r,-1.2),(R.uniform(.07,.23),R.uniform(.08,.25),R.uniform(.06,.16)),i+1)
# Thin mineral seams across the exposed front face.
for z in [-.58,-.79,-1.02]:
    pts=[(-3+j*.25,-3.097,z+.03*math.sin(j*.7)) for j in range(25)]
    line('Oxidised seam',pts,.012,ochre,'01_Rock_cutaway')
floor=material('Studio ground / blue charcoal',(.003,.006,.010),.0,.85)
cube('Dark surround',(0,0,-1.45),(200,200,.18),floor,'01_Rock_cutaway',0)

# Steel guides maintain the original 1.5 m layer spacing.
for x,y in [(-2.77,-2.65),(-2.77,2.67),(2.77,2.67)]:
    cube('Vertical I-beam web',(x,y,1.17),(.12,.18,4.1),steel)
    for dx in [-.11,.11]:cube('I-beam flange',(x+dx,y,1.17),(.06,.27,4.1),edge)
    for z in [-.25,1.27,2.8]:
        cube('Riveted node',(x,y-.15,z),(.4,.08,.28),steel)
        for dx in [-.12,.12]:
            o=cylinder('Hex anchor',(x+dx,y-.2,z),.045,.04,edge,vertices=6);o.rotation_euler[0]=math.pi/2
# Near right support lies outside the board and provides a visible fragment collision.
cube('Impact-side short support',(2.79,-1.0,.60),(.18,.23,1.7),steel)
for z in [-.16,1.34]:
    deckgroup='04_Upper_board' if z>1 else '02_Steel_structure'
    for y in [-2.65,2.65]:cube('Layer crossbeam',(0,y,z),(5.72,.16,.23),steel,deckgroup)
    for x in [-2.65,2.65]:cube('Layer sidebeam',(x,0,z),(.16,5.42,.23),steel,deckgroup)
    for x in [-2,0,2]:cube('Underslung joist',(x,0,z-.14),(.12,5.15,.13),dark,deckgroup)
    for x in [-2.68,2.68]:
        for y in [-2.65,2.65]:cylinder('Deck fixing',(x,y,z+.14),.06,.025,edge,deckgroup,vertices=6)
beam('Rear diagonal brace',(-2.6,2.72,.02),(2.6,2.72,1.22),.09)
beam('Rear diagonal return',(-2.6,2.75,1.30),(2.6,2.75,2.7),.08)
cube('Rear overhead tie',(0,2.72,3.08),(5.7,.22,.22),steel)
line('Power cable',[(-2.65,2.53,3.15),(-1.8,2.56,2.77),(0,2.56,2.59),(1.8,2.56,2.76),(2.65,2.53,3.15)],.028,dark)
for x,z in [(-2.53,.72),(2.53,.72),(-1.65,2.72),(1.62,2.72)]:
    y=2.38
    cylinder('Lamp housing',(x,y,z),.105,.33,dark,'05_Practical_lights')
    cylinder('Amber frosted lamp',(x,y-.018,z),.077,.25,lampmat,'05_Practical_lights')
    for dz in [-.14,.14]:cylinder('Lamp rim',(x,y,z+dz),.118,.04,edge,'05_Practical_lights')
    for a in range(4):
        th=a*math.pi/2
        line('Lamp protection cage',[(x+.102*math.cos(th),y+.102*math.sin(th),z-.15),(x+.102*math.cos(th),y+.102*math.sin(th),z+.15)],.009,edge,'05_Practical_lights')
    point('Practical amber glow',(x,y-.25,z),(1,.48,.17),45,.28)
# Safety ticks along front rails, do not resemble selectable cells.
for z in [.01,1.51]:
    for i in range(13):
        o=cube('Safety stripe',(-2.4+i*.4,-2.745,z),(.12,.012,.07),ochre,'04_Upper_board' if z>1 else '02_Steel_structure',bevel=.004);o.rotation_euler[1]=-.3

mines=[{(4,1),(1,0),(2,2),(3,4)},{(0,1),(2,1),(4,4),(1,3)}]
opened=[{(0,0),(0,1),(0,2),(1,1),(1,2),(2,0),(3,0),(3,1),(4,0)}, {(0,0),(1,0),(2,0),(1,1),(2,2),(3,1)}]
def count(i,j,l):
    return sum((a,b) in mines[c] for a,b,c in [(i-1,j,l),(i+1,j,l),(i,j-1,l),(i,j+1,l),(i,j,1-l)] if 0<=a<5 and 0<=b<5)
tileparts={};openparts={}
def make_open(i,j,l):
    x,y,z=i-2,j-2,l*1.5;g='03_Lower_board' if l==0 else '04_Upper_board';obs=[]
    obs.append(cube('Open inset L%d_%d_%d'%(l,i,j),(x,y,z+.09),(.79,.79,.055),openmat,g,.04))
    n=count(i,j,l)
    if n:obs.append(text_obj('Clue %d at %d %d %d'%(n,i,j,l),str(n),(x,y,z+.123),.52,clue,g))
    else:
        o=cylinder('Zero clear marker',(x,y,z+.123),.047,.008,edge,g);obs.append(o)
    return obs
for l in range(2):
    g='03_Lower_board' if l==0 else '04_Upper_board';z=l*1.5
    for j in range(5):
        for i in range(5):
            x,y=i-2,j-2
            cube('Cell socket L%d_%d_%d'%(l,i,j),(x,y,z-.025),(.93,.93,.12),dark,g,.035)
            parts=[]
            if (i,j) not in opened[l]:
                parts.append(cube('Plate L%d_%d_%d'%(l,i,j),(x,y,z+.2),(.91,.91,.4),steel,g,.045))
                parts.append(cube('Inset lid L%d_%d_%d'%(l,i,j),(x,y,z+.411),(.76,.76,.032),tile,g,.03))
                # A short machined seam, plus exposed corner bolt heads.
                parts.append(cube('Lid seam',(x,y,z+.431),(.38,.018,.004),dark,g,.002))
                for dx,dy in [(-.34,-.34),(.34,-.34),(-.34,.34),(.34,.34)]:
                    parts.append(cylinder('Plate bolt',(x+dx,y+dy,z+.414),.033,.018,edge,g,6))
            else:openparts[i,j,l]=make_open(i,j,l)
            tileparts[i,j,l]=parts
uppermats={}
for o in COL['04_Upper_board'].objects:
    for slot in o.material_slots:
        base=slot.material
        if base.name not in uppermats:
            m=base.copy();m.name=base.name+' / upper fade';nt=m.node_tree
            out=next(n for n in nt.nodes if n.type=='OUTPUT_MATERIAL');p=out.inputs['Surface'].links[0].from_socket
            tr=nt.nodes.new('ShaderNodeBsdfTransparent');mix=nt.nodes.new('ShaderNodeMixShader');nt.links.new(p,mix.inputs[1]);nt.links.new(tr.outputs[0],mix.inputs[2]);nt.links.new(mix.outputs[0],out.inputs['Surface'])
            mix.inputs[0].default_value=0;mix.inputs[0].keyframe_insert('default_value',frame=115)
            mix.inputs[0].default_value=1;mix.inputs[0].keyframe_insert('default_value',frame=145)
            uppermats[base.name]=m
        slot.material=uppermats[base.name]
    hide_at(o,146)

# Lower-board interaction: select, open, flag, then a clearly located loss.
for o in tileparts[2,1,0]:hide_at(o,193)
for o in make_open(2,1,0):hide_before(o,193)
def selection(name,x,y,z,start,end,mat=teal):
    obs=[]
    for dx,dy,sx,sy in [(0,-.49,1,.035),(0,.49,1,.035),(-.49,0,.035,1),(.49,0,.035,1)]:
        o=cube(name,(x+dx,y+dy,z),(sx,sy,.035),mat,'06_Selection',.012);hide_before(o,start);hide_at_after(o,end);obs.append(o)
    return obs
def hide_at_after(o,f):
    o.hide_render=False;key(o,'hide_render',f-1);o.hide_render=True;key(o,'hide_render',f)
    o.hide_viewport=False;key(o,'hide_viewport',f-1);o.hide_viewport=True;key(o,'hide_viewport',f)
safe_selection=selection('Selected safe cell',0,-1,.45,169,241)
for o in safe_selection:
    o.location.z=.45;key(o,'location',192)
    o.location.z=.15;key(o,'location',196)
selection('Selected flag cell',-1,-2,.45,241,291)
selection('Selected danger cell',2,-1,.45,313,337)
# Flag mast and curved cloth, unmistakable without colour.
flagobs=[]
flagobs.append(cylinder('Flag base',(-1,-2,.46),.105,.07,ochre,'03_Lower_board'))
flagobs.append(cylinder('Flag mast',(-1,-2,.85),.021,.76,edge,'03_Lower_board'))
verts=[(-1,-2,1.2),(-.55,-2.02,1.13),(-.51,-1.99,.86),(-1,-2,.94),(-.77,-2.07,1.17),(-.76,-2.06,.91)]
me=bpy.data.meshes.new('Fabric folds');me.from_pydata(verts,[],[(0,4,5,3),(4,1,2,5)]);me.materials.append(gold)
ob=bpy.data.objects.new('Amber flag cloth',me);COL['03_Lower_board'].objects.link(ob);flagobs.append(ob)
for o in flagobs:hide_before(o,251)

# Crater and fractured lip replace the hit tile at the same coordinate.
for o in tileparts[4,1,0]:hide_at(o,HIT)
crater=cylinder('Charred impact cavity',(2,-1,.005),.42,.10,black,'08_Dust_and_flash',32);hide_before(crater,HIT)
for i in range(9):
    a=math.tau*i/9+R.uniform(-.15,.15)
    ob=rockmesh('Broken rim %02d'%i,(2+.39*math.cos(a),-1+.39*math.sin(a),.08),(.15,.12,.035),i+40,'07_Blast_fragments',sub=1);ob.rotation_euler=(R.uniform(-.2,.2),R.uniform(-.2,.2),a);ob.data.materials.clear();ob.data.materials.append(steel);hide_before(ob,HIT)
for i in range(6):
    a=R.random()*math.tau
    ob=cube('Residual ember',(2+R.uniform(.12,.28)*math.cos(a),-1+R.uniform(.12,.28)*math.sin(a),.065),(.035,.025,.015),ember,'08_Dust_and_flash',.008);hide_before(ob,HIT+5)

# Heavy fragments use ballistic integration, rail collision, floor restitution and friction.
# Exported positions are reusable as authored mobile VFX; not a weapons simulation.
trajectory={}; collision_times=[]
for i in range(42):
    size=R.uniform(.07,.17) if i<15 else R.uniform(.018,.065)
    p=Vector((2+R.uniform(-.23,.23),-1+R.uniform(-.23,.23),.36+R.uniform(0,.12)))
    a=R.uniform(0,math.tau);speed=R.uniform(1.0,3.2)
    v=Vector((math.cos(a)*speed,math.sin(a)*speed,R.uniform(2.6,5.2)))
    if i<4:v=Vector((R.uniform(2.6,3.8),R.uniform(-.15,.15),R.uniform(1.8,2.6)))
    ob=rockmesh('Ballistic fragment %02d'%i,p,(size*1.45,size*.85,size*(.24 if i<15 else .56)),i+70,'07_Blast_fragments',sub=1 if i<15 else 2)
    ob.data.materials.clear();ob.data.materials.append(steel if i<15 else char)
    hide_before(ob,HIT);points=[];spin=Vector((R.uniform(-7,7),R.uniform(-7,7),R.uniform(-7,7)));angle=Vector((0,0,0));resting=False
    for f in range(HIT,HIT+122):
        dt=1/FPS
        if f>HIT and not resting:
            angle+=spin*dt
            old=p.copy();v.z-=9.81*dt;p+=v*dt
            # Distinct near-side steel support at x=2.79, y=-1.
            if old.x<2.68<=p.x and abs(p.y+1)<.21 and -.1<p.z<1.46:
                p.x=2.67;v.x=-abs(v.x)*.48;v.y+=R.uniform(-.5,.5);collision_times.append((i,(f-HIT)/FPS,'steel support'))
            floorz=-1.36
            if abs(p.x)<3.08 and abs(p.y)<3.0:floorz=-.365
            if abs(p.x)<2.5 and abs(p.y)<2.5:
                ix=int(math.floor(p.x+2.5));iy=int(math.floor(p.y+2.5))
                if abs(p.x-(ix-2))<.465 and abs(p.y-(iy-2))<.465:
                    floorz=.123 if (ix,iy) in opened[0] or (ix,iy)==(2,1) else .43
                if (ix,iy)==(4,1):floorz=.06
            rot=Euler(tuple(angle),'XYZ').to_matrix()
            support=-min((rot @ Vector((vert.co.x*ob.scale.x,vert.co.y*ob.scale.y,vert.co.z*ob.scale.z))).z for vert in ob.data.vertices)
            if p.z-support<floorz:
                p.z=floorz+support
                if abs(v.z)>.6:collision_times.append((i,(f-HIT)/FPS,'deck'))
                v.z=abs(v.z)*.24;v.x*=.74;v.y*=.74;spin*=.72
                if abs(v.z)<.18:v.z=0
                if math.hypot(v.x,v.y)<.12 and abs(v.z)<.16:
                    v=Vector((0,0,0));spin=Vector((0,0,0));resting=True
        ob.location=p;ob.rotation_euler=tuple(angle);key(ob,'location',f);key(ob,'rotation_euler',f)
        points.append([f,*map(float,p),*map(float,angle)])
    trajectory[ob.name]=points

# Local flash lights adjacent materials; no full-screen white card.
flash=point('Blast light at actual cell',(2,-1,.75),(1,.54,.20),0,.18)
for f,power in [(1,0),(HIT-1,0),(HIT,3600),(HIT+2,1500),(HIT+5,280),(HIT+10,0)]:flash.data.energy=power;flash.data.keyframe_insert('energy',frame=f)
hot=material('Initial hot core',(1,.37,.05),0,.4,16)
ob=rockmesh('Short luminous ignition',(2,-1,.52),(.01,.01,.01),91,'08_Dust_and_flash');ob.data.materials.clear();ob.data.materials.append(hot);hide_before(ob,HIT);hide_at_after(ob,HIT+6)
for f,sc in [(HIT,.12),(HIT+1,.40),(HIT+3,.28),(HIT+5,.06)]:ob.scale=(sc,sc,sc*.7);key(ob,'scale',f)

def dust_material(name,density,color):
    m=bpy.data.materials.new(name);m.use_nodes=True;nt=m.node_tree;nt.nodes.clear();out=nt.nodes.new('ShaderNodeOutputMaterial');v=nt.nodes.new('ShaderNodeVolumePrincipled');v.inputs['Color'].default_value=(*color,1);v.inputs['Anisotropy'].default_value=.12
    coord=nt.nodes.new('ShaderNodeTexCoord');dist=nt.nodes.new('ShaderNodeVectorMath');dist.operation='DISTANCE';nt.links.new(coord.outputs['Generated'],dist.inputs[0]);dist.inputs[1].default_value=(.5,.5,.5)
    ramp=nt.nodes.new('ShaderNodeMapRange');ramp.inputs['From Min'].default_value=.16;ramp.inputs['From Max'].default_value=.50;ramp.inputs['To Min'].default_value=1;ramp.inputs['To Max'].default_value=0;nt.links.new(dist.outputs['Value'],ramp.inputs[0])
    tex=nt.nodes.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=5.8;tex.inputs['Detail'].default_value=3.2;tex.inputs['Roughness'].default_value=.7
    mul=nt.nodes.new('ShaderNodeMath');mul.operation='MULTIPLY';nt.links.new(ramp.outputs[0],mul.inputs[0]);nt.links.new(tex.outputs['Fac'],mul.inputs[1])
    den=nt.nodes.new('ShaderNodeMath');den.operation='MULTIPLY';nt.links.new(mul.outputs[0],den.inputs[0]);den.inputs[1].default_value=density;nt.links.new(den.outputs[0],v.inputs['Density']);nt.links.new(v.outputs[0],out.inputs['Volume'])
    for f,value in [(1,0),(HIT,0),(HIT+4,density),(HIT+16,density*.76),(HIT+48,density*.27),(HIT+96,density*.07),(HIT+144,0)]:den.inputs[1].default_value=value;den.inputs[1].keyframe_insert('default_value',frame=f)
    return m
for i in range(13):
    a=math.tau*i/13
    mat=dust_material('Dust lobe %02d'%i,8.0 if i<6 else 5.8,(.28,.23,.17))
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=1,location=(2,-1,.42));o=bpy.context.object;o.name='Expanding mineral dust %02d'%i;o.data.materials.append(mat);put(o,'08_Dust_and_flash');hide_before(o,HIT);hide_at_after(o,HIT+145)
    for f,k in [(HIT,0),(HIT+8,.24),(HIT+24,.65),(HIT+60,1),(HIT+144,1.5)]:
        o.location=(2+math.cos(a)*k*.75,-1+math.sin(a)*k*.75,.45+k*(.85 if i%2 else 1.22));sc=.08+k*(.62 if i<6 else .48);o.scale=(sc,sc,sc*.9);key(o,'location',f);key(o,'scale',f)

area('Cool overhead softbox',(1,-2,8),(0,0,.5),(.58,.76,1),900,7)
area('Slate blue rim',(-4,2,5),(0,0,1),(.29,.55,1),750,5)
area('Warm grazing fill',(5,-1,4),(0,0,.5),(1,.67,.40),320,4)
area('Front reading light',(1,-6,5),(0,0,.3),(.72,.87,1),300,5)

camdata=bpy.data.cameras.new('Game camera · 40 degree vertical FOV');cam=bpy.data.objects.new('Game camera',camdata);COL['09_Cameras'].objects.link(cam);s.camera=cam
camdata.sensor_fit='VERTICAL';camdata.sensor_height=24;camdata.lens=12/math.tan(math.radians(20));camdata.clip_start=.1;camdata.clip_end=250
def camera_pose(frame,yaw,pitch,distance,cz):
    ya=math.radians(yaw);pi=math.radians(pitch);target=Vector((0,0,cz));cam.location=target+Vector((math.sin(ya)*math.cos(pi),-math.cos(ya)*math.cos(pi),math.sin(pi)))*distance
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();key(cam,'location',frame);key(cam,'rotation_euler',frame)
for values in [(1,63,35,25.0,.75),(49,47,39,24.0,.60),(97,36,43,23.0,.45),(115,36,43,23.0,.45),(145,36,43,23.0,.30),(HIT-1,36,43,23.0,.30),(HIT,36.5,43.3,23.0,.30),(HIT+2,35.7,42.8,23.0,.30),(HIT+4,36.15,43.08,23.0,.30),(HIT+7,36,43,23.0,.30),(576,36,43,23.0,.30)]:camera_pose(*values)
# Editable timeline markers and soundtrack are included in the blend.
for frame,label in [(1,'01 · Orbit / all layers'),(116,'02 · Switch to layer 01'),(169,'03 · Select safe cell'),(193,'04 · Open / clue 2'),(251,'05 · Plant flag'),(313,'06 · Select mine cell'),(337,'07 · Impact'),(361,'08 · Debris / collision'),(433,'09 · Dust settling'),(481,'10 · Clear aftermath')]:s.timeline_markers.new(label,frame=frame)
seq=s.sequence_editor_create()
strips=seq.strips if hasattr(seq,'strips') else seq.sequences
for ch,name in enumerate(['ambience','interaction','impact','low','debris','cavern'],1):
    strips.new_sound(name,str(ROOT/'audio/stems'/(name+'.wav')),channel=ch,frame_start=1)
s.render.use_sequencer=False

# Save source contracts for Android phase 2, without modifying Android code.
(ROOT/'fragment_trajectories.json').write_text(json.dumps({'fps':FPS,'hit_frame':HIT,'sample_fields':['frame','x','y','z','rotation_x_rad','rotation_y_rad','rotation_z_rad'],'trajectories':trajectory,'collisions':collision_times},indent=2),encoding='utf8')
(ROOT/'scene_contract.json').write_text(json.dumps({'grid':[5,5,2],'cell_pitch':1,'tile_size':.91,'layer_gap':1.5,'camera':{'yaw_degrees':36,'pitch_degrees':43,'vertical_fov':40,'focus_distance':23.0},'axis_mapping':'Android world (x,y,z) = Blender world (x,z,-y). Authoring row j maps to Android board row 4-j; mirror all rows together, not only the hit cell.','active_layer':0,'hit_cell':[4,1,0],'safe_open_cell':[2,1,0],'safe_open_clue':count(2,1,0),'mines':[sorted(m) for m in mines],'android_cells':{'hit':[4,3,0],'safe_open':[2,3,0],'mines':[sorted((i,4-j) for i,j in m) for m in mines]},'render_only':'Blender Cycles target. Shader nodes and volumetric dust are not automatically compatible with OpenGL ES 2.'},ensure_ascii=False,indent=2),encoding='utf8')
s['phase']='Phase 1 visual target, Android integration pending user confirmation'
s['audio_sync']='Frame337 = 14.000 s, exact hit origin (2,-1,0)'
s['font_license']='Noto Sans / Noto Sans SC · SIL OFL 1.1'
s.frame_set(220)
for a in bpy.context.screen.areas if bpy.context.screen else []:
    if a.type=='VIEW_3D':
        a.spaces.active.region_3d.view_perspective='CAMERA'
        a.spaces.active.shading.type='MATERIAL'
        a.spaces.active.shading.use_scene_world=True
        a.spaces.active.shading.use_scene_lights=True
        a.spaces.active.overlay.show_overlays=False
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Mines3D_DeepSector.blend'))
print('SAVED',str(ROOT/'Mines3D_DeepSector.blend'),'OBJECTS',len(s.objects),'COLLISIONS',len(collision_times))
