"""Package runtime derivatives of original licensed art/audio, retaining originals."""
from pathlib import Path
import json,shutil,subprocess
import numpy as np
from scipy.io import wavfile
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parents[1]/'app/src/main/assets/mine';OUT.mkdir(parents=True,exist_ok=True)
FF=Path(r'C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Packages\yt-dlp.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-N-124279-g0f6ba39122-win64-gpl\bin\ffmpeg.exe')
for name in ['rock_basecolor','steel_basecolor','rock_normal']:
    Image.open(ROOT/'textures'/(name+'.png')).convert('RGB').resize((512,512),Image.Resampling.LANCZOS).save(OUT/(name+'.png'))
for name in ['NotoSansSC-OFL.txt','NotoSans-Bold.ttf','NotoSans-OFL.txt']:
    shutil.copyfile(ROOT/'fonts'/name,OUT/name)
if not (OUT/'NotoSansSC-Medium.ttf').exists():
    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont
    font=instantiateVariableFont(TTFont(ROOT/'fonts/NotoSansSC-VF.ttf'),{'wght':500},inplace=True)
    font.save(OUT/'NotoSansSC-Medium.ttf')
for name in ['select','open','flag','layer']:
    subprocess.run([str(FF),'-v','error','-y','-i',str(ROOT/'audio'/(name+'.wav')),'-c:a','pcm_s16le',str(OUT/(name+'.wav'))],check=True)
subprocess.run([str(FF),'-v','error','-y','-i',str(ROOT/'audio/ambience_loop.wav'),'-c:a','libvorbis','-q:a','5',str(OUT/'ambience.ogg')],check=True)
parts=[]
for name in ['impact','low','debris','cavern']:
    sr,a=wavfile.read(ROOT/'audio/stems'/(name+'.wav'));parts.append(a.astype(np.float64)/2147483648.)
blast=sum(parts)[14*sr:];blast*=min(1.7,.83/max(.00001,np.abs(blast).max()))
wavfile.write(OUT/'blast.wav',sr,np.int16(np.clip(blast,-1,1)*32767))
# Soft volumetric impostor, sampled from the same dust palette. Renderer places
# animated camera-facing lobes in world space with depth testing and no depth writes.
rng=np.random.default_rng(20261112);n=256;y,x=np.mgrid[-1:1:complex(n),-1:1:complex(n)]
from scipy.ndimage import gaussian_filter
noise=gaussian_filter(rng.random((n,n)),4);noise=(noise-noise.min())/(noise.max()-noise.min())
alpha=np.clip(1-np.sqrt(x*x+y*y),0,1)**1.6*(.55+.45*noise)
rgba=np.zeros((n,n,4),dtype=np.uint8);rgba[:,:,:3]=(128,115,96);rgba[:,:,3]=np.uint8(alpha*210)
Image.fromarray(rgba).save(OUT/'dust.png')
atlas=Image.new('RGBA',(1024,1024))
for i in range(16):atlas.paste(Image.open(ROOT/'mobile/dust'/('%02d.png'%i)).convert('RGBA'),((i%4)*256,(i//4)*256))
atlas.save(OUT/'dust_atlas.png')
(OUT/'LICENSES.txt').write_text('Mines3D mine scene and sound effects: original procedural project assets.\nSource: art/mine_scene, with editable Blender scene and generation scripts.\nFonts: Noto Sans / Noto Sans SC, SIL Open Font License 1.1; license files included.\n',encoding='utf8')
print('ANDROID_ASSETS_READY',OUT)
