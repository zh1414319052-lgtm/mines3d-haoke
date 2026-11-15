"""Inspect the actual Android playback capture, not the Blender movie."""
from pathlib import Path
import subprocess,json,sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import correlate
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];REVIEW=ROOT/'review'
FF=Path(r'C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Packages\yt-dlp.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-N-124279-g0f6ba39122-win64-gpl\bin\ffmpeg.exe')
capture=REVIEW/(sys.argv[1] if len(sys.argv)>1 else 'qa-sound.mkv')
suffix='-final' if 'final' in capture.stem else ''
raw=subprocess.check_output([str(FF),'-v','error','-i',str(capture),'-map','0:a:0','-f','f32le','-ar','48000','-ac','2','pipe:1'])
audio=np.frombuffer(raw,dtype='<f4').reshape(-1,2)
rate,source=wavfile.read(ROOT.parents[1]/'app/src/main/assets/mine/blast.wav')
mono=audio.mean(axis=1);ref=source.astype(float).mean(axis=1)/32768
template=ref[:24000];cross=correlate(mono,template,method='fft',mode='valid');offset=int(np.argmax(cross))
segment=mono[offset:offset+len(template)];corr=float(np.dot(segment,template)/(np.linalg.norm(segment)*np.linalg.norm(template)))
onset=offset/48000
metrics={'source':'PKG110 playback capture, scrcpy 4.1, AAC stereo 48kHz','duration_audio_seconds':len(audio)/48000,'peak_dbfs':float(20*np.log10(max(1e-9,np.abs(audio).max()))),'samples_at_or_over_0dbfs':int(np.sum(np.abs(audio)>=1)),'blast_template_onset_seconds':onset,'first_half_second_normalized_correlation':corr,'note':'Digital playback capture confirms actual device output. This does not measure physical speaker sound or acoustics.'}
font=ImageFont.truetype(str(ROOT/'fonts/NotoSans-Bold.ttf'),14)
contact=Image.new('RGB',(6*220,515),(12,20,29))
for i,delta in enumerate([-.15,-.05,0,.05,.15,.45]):
    t=max(0,onset+delta)
    frame=subprocess.check_output([str(FF),'-v','error','-ss',str(t),'-i',str(capture),'-frames:v','1','-vf','scale=220:-1','-f','image2pipe','-vcodec','png','pipe:1'])
    import io
    im=Image.open(io.BytesIO(frame)).convert('RGB');contact.paste(im,(i*220,28));ImageDraw.Draw(contact).text((i*220+8,7),'%.3f s'%t,font=font,fill=(233,209,165))
contact.save(REVIEW/('phone-blast-sync'+suffix+'.jpg'),quality=84)
(REVIEW/('phone-audio-check'+suffix+'.json')).write_text(json.dumps(metrics,indent=2),encoding='utf8')
print(json.dumps(metrics,indent=2))
