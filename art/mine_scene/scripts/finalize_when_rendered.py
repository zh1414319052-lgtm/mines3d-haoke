"""One-shot task pipeline: wait for this render, encode, decode, inspect metadata.
It does not install a scheduler or send messages, and never deletes files.
"""
import os,sys,time,json,subprocess,re,hashlib
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
FF=Path(r'C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Packages\yt-dlp.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-N-124279-g0f6ba39122-win64-gpl\bin\ffmpeg.exe')
FP=FF.with_name('ffprobe.exe')
env=os.environ.copy();env['FFMPEG_BIN']=str(FF)
work=ROOT/'review/encode_work';work.mkdir(exist_ok=True);env['TEMP']=str(work);env['TMP']=str(work)
def run(cmd,log):
    with (ROOT/log).open('w',encoding='utf8') as out:
        p=subprocess.run([str(v) for v in cmd],stdout=out,stderr=subprocess.STDOUT,env=env)
    if p.returncode:raise RuntimeError(f'{log}: exit {p.returncode}')
while True:
    flag=ROOT/'render_complete.json'
    if flag.exists():
        try:
            status=json.loads(flag.read_text(encoding='utf8'))
            if status.get('finished') and status.get('source_sha')==hashlib.sha256((ROOT/'Mines3D_DeepSector.blend').read_bytes()).hexdigest():break
        except (OSError,json.JSONDecodeError):pass
    time.sleep(30)
print('All render frames are ready; composing lossless reference',flush=True)
run([sys.executable,ROOT/'scripts/compose_movie.py','reference'],'finalize-reference.log')
reference_sha=hashlib.sha256((ROOT/'review/blast_reference.mkv').read_bytes()).hexdigest()
report=ROOT/('encode-bench-'+reference_sha[:12]+'.json')
if not report.exists():
    run([sys.executable,r'C:\Users\Administrator\.claude\skills\video-render-quality\scripts\encode_bench.py',ROOT/'review/blast_reference.mkv','--report',report,'--ffmpeg',FF,'--threads','6','--keep'],'encode-benchmark.log')
bench=json.loads(report.read_text(encoding='utf8'));bench['reference_sha256']=reference_sha
(ROOT/'encode-bench.json').write_text(json.dumps(bench,ensure_ascii=False,indent=2),encoding='utf8')
args=bench['recommend_args'];env['MINES_ENCODE_TUNE']=args[args.index('-tune')+1]
print('Selected encoding',bench['recommend'],flush=True)
run([sys.executable,ROOT/'scripts/compose_movie.py','final'],'finalize-encode.log')
video=ROOT.parents[2]/'三维扫雷_矿井爆炸_第一阶段样片.mp4'
result=subprocess.run([str(FP),'-v','error','-show_format','-show_streams','-of','json',str(video)],capture_output=True,text=True,encoding='utf8',check=True)
probe=json.loads(result.stdout);v=next(x for x in probe['streams'] if x['codec_type']=='video');a=next(x for x in probe['streams'] if x['codec_type']=='audio')
assert (v['width'],v['height'],v['r_frame_rate'],v['nb_frames'])==(1080,1920,'24/1','576')
assert all(v[k]=='bt709' for k in ['color_space','color_transfer','color_primaries']) and v['color_range']=='tv'
assert a['sample_rate']=='48000' and a['channels']==2
assert abs(float(probe['format']['duration'])-24)<.05
run([FF,'-v','error','-i',video,'-f','null','NUL'],'review/full-decode.log')
loud=subprocess.run([str(FF),'-hide_banner','-i',str(video),'-af','loudnorm=I=-18:TP=-1.5:LRA=9:print_format=json','-f','null','NUL'],capture_output=True,text=True,errors='replace',check=True)
stats=json.loads(re.search(r'\{\s*"input_i".*?\}',loud.stderr,re.S).group())
frames=[1,97,146,169,193,251,313,337,340,350,360,370,400,433,482,576]
outdir=ROOT/'review/final_frames';outdir.mkdir(exist_ok=True)
select='+'.join(f'eq(n,{f-1})' for f in frames)
run([FF,'-hide_banner','-y','-i',video,'-vf',f"select='{select}',scale=540:960:flags=lanczos",'-fps_mode','vfr','-q:v','2',outdir/'frame_%02d.jpg'],'review/frame-extract.log')
sheet=Image.new('RGB',(1080,2000),(9,16,22));font=ImageFont.truetype(str(ROOT/'fonts/NotoSans-Bold.ttf'),16)
for k,f in enumerate(frames):
    im=Image.open(outdir/('frame_%02d.jpg'%(k+1)));im=im.resize((270,480),Image.Resampling.LANCZOS)
    x=(k%4)*270;y=(k//4)*500;sheet.paste(im,(x,y));ImageDraw.Draw(sheet).text((x+8,y+482),f'{(f-1)/24:05.2f}s / F{f}',font=font,fill='white')
sheet.save(ROOT/'review/final-contact-sheet.jpg',quality=88)
checks={'status':'PASS','video':str(video),'sha256':hashlib.sha256(video.read_bytes()).hexdigest().upper(),'format':probe,'final_loudness':stats,'full_decode':'PASS','font_license':'Noto / SIL OFL 1.1','manual_review':'Pending viewing decoded final frames and sound/video','not_tested':['Android integration','Physical phone playback / speaker listening','Device frame rate','Five gameplay modes (phase 2)']}
(ROOT/'review/video-verification.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf8')
print('FINAL_ENCODE_READY',str(video),flush=True)
