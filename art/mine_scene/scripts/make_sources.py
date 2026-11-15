"""Original procedural textures, SFX and camera-space graphics. Noto Sans SC / OFL.
No samples, stock photos or external recordings are used. Reproducible seed 20261112.
"""
from pathlib import Path
import json, wave, shutil
import numpy as np
from scipy import signal, ndimage
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
RNG=np.random.default_rng(20261112)
SR=48000; DURATION=24; FPS=24
for d in ['textures','audio/stems','fonts','review','renders','graphics']:
    (ROOT/d).mkdir(parents=True,exist_ok=True)
fontsrc=ROOT/'fonts/NotoSansSC-VF.ttf'
if not fontsrc.exists():fontsrc=Path('C:/Windows/Fonts/NotoSansSC-VF.ttf')
assert fontsrc.exists(), 'Commercial font is required'
if fontsrc.resolve()!=(ROOT/'fonts/NotoSansSC-VF.ttf').resolve():shutil.copyfile(fontsrc,ROOT/'fonts/NotoSansSC-VF.ttf')
if not (ROOT/'fonts/NotoSans-Bold.ttf').exists():shutil.copyfile('C:/Windows/Fonts/NotoSans-Bold.ttf',ROOT/'fonts/NotoSans-Bold.ttf')

def fbm(size=1024):
    out=np.zeros((size,size))
    for coarse,weight in [(5,.32),(13,.25),(35,.18),(91,.13),(250,.08),(1024,.04)]:
        v=RNG.random((coarse,coarse))
        out+=np.asarray(Image.fromarray(v.astype('float32')).resize((size,size),Image.Resampling.BICUBIC))*weight
    return np.clip(out,0,1)
h=fbm(); y,x=np.mgrid[:1024,:1024]/1024
strata=(np.sin(y*90+h*19)*.5+.5)*.08
rock=h*.8+strata
base=np.stack([rock*.28+.08,rock*.34+.10,rock*.40+.13],axis=-1)
Image.fromarray((np.clip(base,0,1)*255).astype('uint8')).save(ROOT/'textures/rock_basecolor.png')
Image.fromarray((np.clip(.75+h*.22,0,1)*255).astype('uint8')).save(ROOT/'textures/rock_roughness.png')
Image.fromarray((rock*65535).astype('uint16')).save(ROOT/'textures/rock_height.png')
dy,dx=np.gradient(rock)
norm=np.stack([-dx*8,-dy*8,np.ones_like(dx)],axis=-1);norm/=np.linalg.norm(norm,axis=-1)[...,None]
Image.fromarray(((norm*.5+.5)*255).astype('uint8')).save(ROOT/'textures/rock_normal.png')
metal=fbm(); scratches=ndimage.gaussian_filter(RNG.random((1024,1024)),(0,30))
coat=np.stack([metal*.055+.09,metal*.065+.14,metal*.075+.18],axis=-1)
coat+=((scratches-.5)*.12)[...,None]
Image.fromarray((np.clip(coat,0,1)*255).astype('uint8')).save(ROOT/'textures/steel_basecolor.png')
Image.fromarray((np.clip(.38+metal*.37,0,1)*255).astype('uint8')).save(ROOT/'textures/steel_roughness.png')

def filt(v,lo=None,hi=None):
    if lo and hi: sos=signal.butter(3,[lo,hi],btype='bandpass',fs=SR,output='sos')
    elif hi:sos=signal.butter(3,hi,btype='lowpass',fs=SR,output='sos')
    else:sos=signal.butter(3,lo,btype='highpass',fs=SR,output='sos')
    return signal.sosfilt(sos,v)
def time(s):return np.arange(round(s*SR))/SR
def mono(v):return np.column_stack([v,v])
def stereo(v,width=.12):
    v=np.asarray(v);return np.column_stack([v,np.roll(v,int(width*SR))*.93])
def fade(v,attack=.003,release=.06):
    a=min(len(v),int(attack*SR));b=min(len(v),int(release*SR));v=v.copy()
    v[:a]*=np.linspace(0,1,a);v[-b:]*=np.linspace(1,0,b)
    return v
def write(name,a):
    a=np.clip(a,-.99,.99)
    with wave.open(str(ROOT/'audio'/name),'wb') as f:
        f.setnchannels(a.shape[1] if a.ndim>1 else 1);f.setsampwidth(3);f.setframerate(SR)
        x=(a*8388607).astype('<i4').reshape(-1);b=x.view('uint8').reshape(-1,4)[:,:3]
        f.writeframes(b.tobytes())

t=time(.13); select=fade((np.sin(2*np.pi*(1450*t-3100*t*t))*.08+filt(RNG.normal(size=len(t)),hi=2800)*.07)*np.exp(-t*48))
t=time(.32); opened=fade((np.sin(2*np.pi*580*t)*.095+np.sin(2*np.pi*870*t)*.055)*np.exp(-t*17)+filt(RNG.normal(size=len(t)),lo=500,hi=2700)*np.exp(-t*55)*.12)
t=time(.38); flag=fade(filt(RNG.normal(size=len(t)),lo=180,hi=2700)*np.exp(-t*22)*.20+np.sin(2*np.pi*(350*t+200*t*t))*np.exp(-t*18)*.07)
t=time(.72); layer=fade(filt(RNG.normal(size=len(t)),lo=240,hi=1300)*np.sin(np.pi*t/.72)**2*.10+np.sin(2*np.pi*(230*t-50*t*t))*np.sin(np.pi*t/.72)**2*.05,release=.12)
t=time(.7); impact=fade((filt(RNG.normal(size=len(t)),lo=180,hi=8000)*1.2*np.exp(-t*21)+filt(RNG.normal(size=len(t)),lo=90,hi=1200)*.65*np.exp(-t*7)),attack=.0005)
t=time(2.2); bass=fade((np.sin(2*np.pi*(64*t+14*(1-np.exp(-t*8))))*.55+np.sin(2*np.pi*132*t)*.11+filt(RNG.normal(size=len(t)),lo=60,hi=290)*.25)*np.exp(-t*2.6),attack=.004)
t=time(4.8); tail=filt(RNG.normal(size=len(t)),lo=150,hi=1700)*np.exp(-t*1.15)*.065
for delay,level,cutoff in [(.035,.28,3300),(.097,.23,2600),(.173,.19,2200),(.281,.14,1800),(.427,.11,1400),(.663,.08,1100),(.971,.055,900),(1.401,.032,700),(1.893,.018,600)]:
    reflection=filt(impact,lo=140,hi=cutoff)*level;k=round(delay*SR)
    tail[k:k+len(reflection)]+=reflection
tail+=(np.sin(2*np.pi*103*t)*.022+np.sin(2*np.pi*157*t)*.012)*np.exp(-t*1.7)*(1-np.exp(-t*18))
tail=fade(tail,attack=.008,release=.6)
debris=np.zeros(round(3.3*SR))
for j,at in enumerate([.13,.21,.29,.40,.48,.62,.80,1.02,1.21,1.55,1.9,2.18,2.51,2.85]):
    d=.10+RNG.random()*.12; tt=time(d)
    v=(filt(RNG.normal(size=len(tt)),lo=600,hi=6200)*.42+np.sin(2*np.pi*RNG.uniform(730,1850)*tt)*.13)*np.exp(-tt*(28+j))
    v=fade(v,attack=.0004,release=.025)*(.92-j*.037);k=round(at*SR);debris[k:k+len(v)]+=v
assets={'select.wav':mono(select),'open.wav':mono(opened),'flag.wav':stereo(flag,.003),'layer.wav':stereo(layer,.018),'blast_impact.wav':mono(impact),'blast_low.wav':mono(bass),'blast_debris.wav':stereo(debris,.011),'blast_cavern.wav':stereo(tail,.047)}
for k,v in assets.items():write(k,v)
N=DURATION*SR;tt=np.arange(N)/SR
air=filt(RNG.normal(size=N),lo=90,hi=850)*.025
air+=np.sin(2*np.pi*108*tt)*.004+np.sin(2*np.pi*217*tt)*.0018
amb=stereo(air,.031)
# Sparse close drips and a distant hollow return, with distinct positions.
for at,pan in [(1.8,-.5),(4.1,.5),(10.2,-.3),(12.4,.4),(21.8,.1)]:
    t=time(.55);v=fade(np.sin(2*np.pi*(1700*t-600*t*t))*np.exp(-t*26)*.025)
    idx=round(at*SR);amb[idx:idx+len(v),0]+=v*(1-pan);amb[idx:idx+len(v),1]+=v*(1+pan)
amb[:SR]*=np.linspace(0,1,SR)[:,None];amb[-SR:]*=np.linspace(1,0,SR)[:,None]
stems={'ambience':amb,'interaction':np.zeros((N,2)),'impact':np.zeros((N,2)),'low':np.zeros((N,2)),'debris':np.zeros((N,2)),'cavern':np.zeros((N,2))}
def place(stem,name,at,gain=1):
    v=assets[name]*gain;i=round(at*SR);n=min(len(v),N-i);stems[stem][i:i+n]+=v[:n]
events=[('layer.wav',4.8),('select.wav',7.0),('open.wav',8.0),('select.wav',10.0),('flag.wav',10.4),('select.wav',13.0)]
for name,at in events:place('interaction',name,at,2.2)
blast=14.0
for stem,name,delay,gain in [('impact','blast_impact.wav',0,.70),('low','blast_low.wav',.015,.67),('debris','blast_debris.wav',0,.65),('cavern','blast_cavern.wav',.08,.8)]:place(stem,name,blast+delay,gain)
stems['ambience']*=2.6
mix=sum(stems.values())
# Shared look-ahead compression preserves the relative stem mix and softens the
# one-sample transient without removing the midrange impact on phone speakers.
envelope=ndimage.maximum_filter1d(np.max(np.abs(mix),axis=1),size=1441)
envelope=ndimage.gaussian_filter1d(envelope,240)
gain=np.minimum(1,(np.maximum(envelope,.001)/.32)**(-.64))[:,None]
gain*=.80/max(.80,np.max(np.abs(mix*gain)))
for k,v in stems.items():write('stems/'+k+'.wav',v*gain)
write('mix_master.wav',mix*gain)
write('ambience_loop.wav',amb)

fontpath=str(ROOT/'fonts/NotoSansSC-VF.ttf')
def font(sz):
    f=ImageFont.truetype(fontpath,sz)
    f.set_variation_by_axes([560 if sz>=38 else 450])
    return f
def ui(state,subtitle):
    im=Image.new('RGBA',(1080,1920));d=ImageDraw.Draw(im)
    # Minimal vertical framing; scene retains most of the canvas.
    d.text((70,100),'M I N E S  /  D E E P  S E C T O R',font=font(23),fill=(183,199,207,235))
    d.text((64,142),'三维扫雷',font=font(70),fill=(241,238,221,255))
    d.line((70,250,166,250),fill=(234,174,74,255),width=4)
    d.text((70,277),subtitle,font=font(26),fill=(184,198,202,255))
    if state=='overview':
        d.text((70,1668),'立体矿井 · 双层探索',font=font(32),fill=(238,232,213,255))
        d.text((70,1728),'旋转观察，逐层推理',font=font(25),fill=(156,180,192,255))
    else:
        d.rounded_rectangle((60,1560,1020,1643),radius=24,fill=(12,24,32,225),outline=(65,87,97,190),width=2)
        d.text((90,1578),'当前层  01 / 02',font=font(30),fill=(227,232,226,255))
        d.text((716,1585),'5 × 5 × 2',font=font(24),fill=(139,178,191,255))
        if state!='blast':
            can_open=state=='play';can_flag=state in ['play','flagged']
            d.rounded_rectangle((60,1670,520,1780),radius=26,fill=(26,74,84,245) if can_open else (22,33,40,235),outline=(77,175,183,255) if can_open else (62,78,85,235),width=2)
            d.rounded_rectangle((550,1670,1020,1780),radius=26,fill=(34,37,35,240),outline=(127,116,81,255) if can_flag else (62,78,85,235),width=2)
            d.text((290,1725),'已打开' if state=='opened' else '开格',anchor='mm',font=font(38),fill=(230,249,242,255) if can_open else (115,135,142,255))
            d.text((785,1725),'取消旗帜' if state=='flagged' else '插旗',anchor='mm',font=font(38),fill=(244,201,119,255) if can_flag else (115,135,142,255))
        else:
            d.text((70,1690),'触雷 · 本次探索结束',font=font(36),fill=(242,182,122,255))
            d.text((70,1752),'保留现场，继续下一次推理',font=font(24),fill=(164,185,192,255))
    im.save(ROOT/'graphics'/('ui_'+state+'.png'))
ui('overview','岩层之间，线索相连')
ui('play','打开安全格，标记危险区域')
ui('idle','单击矿板选择一个格子')
ui('opened','安全开格 · 提示来自六个相邻方向')
ui('flagged','旗帜已放置 · 再次点击可取消')
ui('blast','危险发生在你选中的那一格')
manifest={'fps':FPS,'frames':576,'duration_seconds':24,'explosion_frame':337,'explosion_seconds':14.0,'coordinates':{'column':4,'row':1,'layer':0,'blender_xyz':[2,-1,0]},'events':events,'audio_format':'48 kHz / 24-bit PCM stereo','audio_source':'Original procedural synthesis in scripts/make_sources.py; no third-party samples','texture_source':'Original deterministic procedural generation','font':'Noto Sans SC and Noto Sans, SIL Open Font License 1.1','timing':'Video frame 1 corresponds to t=0; blast occurs on frame 337 / t=14.000s'}
(ROOT/'timeline.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
print('CREATED original textures, eight one-shots, ambience, six stems, master mix and UI plates')
