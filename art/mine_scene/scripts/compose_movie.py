"""Single final lossy encode from original 16-bit Blender PNGs and PCM mix.
Creates a lossless 5-second reference first for encoder quality comparison.
"""
from pathlib import Path
import json,subprocess,sys,shutil,os,re
ROOT=Path(__file__).resolve().parents[1]
FF=Path(os.environ.get('FFMPEG_BIN',r'C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Packages\yt-dlp.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-N-124279-g0f6ba39122-win64-gpl\bin\ffmpeg.exe'))
mode=sys.argv[1] if len(sys.argv)>1 else 'final'
mapping=json.loads((ROOT/'frame_map.json').read_text(encoding='utf8'))
def concat(frames,path):
    lines=['ffconcat version 1.0']
    for f in frames:
        file=(ROOT/'renders'/('%04d.png'%mapping[str(f)])).as_posix()
        assert Path(file).exists(),file
        lines+=['file '+"'"+file+"'",'duration 0.041666666666667']
    lines+=['file '+"'"+file+"'"]
    path.write_text('\n'.join(lines)+'\n',encoding='utf8')
frame_limit=168 if mode=='preview' else 576
seq=ROOT/('reference.ffconcat' if mode=='reference' else 'intro_preview.ffconcat' if mode=='preview' else 'movie.ffconcat')
frames=range(337,457) if mode=='reference' else range(1,frame_limit+1)
concat(frames,seq)
def run(args):
    r=subprocess.run([str(FF),'-hide_banner','-y',*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf8',errors='replace')
    (ROOT/('encode_'+mode+'.log')).write_text(r.stderr,encoding='utf8')
    if r.returncode:raise RuntimeError(r.stderr[-3000:])
if mode=='reference':
    run(['-safe','0','-r','24','-f','concat','-i',str(seq),'-vf','fps=24,format=gbrp16le','-frames:v','120','-c:v','ffv1','-level','3','-pix_fmt','gbrp16le',str(ROOT/'review/blast_reference.mkv')])
else:
    measurement=subprocess.run([str(FF),'-hide_banner','-i',str(ROOT/'audio/mix_master.wav'),'-af','loudnorm=I=-18:TP=-1.5:LRA=9:print_format=json','-f','null','NUL'],capture_output=True,text=True,errors='replace',check=True)
    loud=json.loads(re.search(r'\{\s*"input_i".*?\}',measurement.stderr,re.S).group())
    (ROOT/'review/loudness-premaster.json').write_text(json.dumps(loud,indent=2),encoding='utf8')
    mastering=f"loudnorm=I=-18:TP=-1.5:LRA=9:measured_I={loud['input_i']}:measured_TP={loud['input_tp']}:measured_LRA={loud['input_lra']}:measured_thresh={loud['input_thresh']}:offset={loud['target_offset']}:linear=false"
    if mode=='preview':mastering+=',afade=t=out:st=6.8:d=0.2'
    report=ROOT/'encode-bench.json';tune='film'
    if report.exists():
        data=json.loads(report.read_text(encoding='utf8'));(ROOT/'encoder_report_used.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
        # Selection is supplied explicitly after inspecting the tool's report.
        tune=os.environ.get('MINES_ENCODE_TUNE','film')
    out=ROOT/'review/intro_progress.mp4' if mode=='preview' else ROOT.parents[2]/'三维扫雷_矿井爆炸_第一阶段样片.mp4'
    states={'overview':[(1,145)],'idle':[(146,168),(291,312)],'play':[(169,192),(241,250),(313,336)],'opened':[(193,240)],'flagged':[(251,290)],'blast':[(337,576)]}
    inputs=[];parts=['[0:v]fps=24,format=rgba[base]'];prior='base'
    for index,(state,ranges) in enumerate(states.items(),1):
        inputs+=['-loop','1','-i',str(ROOT/'graphics'/('ui_'+state+'.png'))]
        condition='+'.join(f'gte(t,{(a-1)/24-1e-6:.9f})*lt(t,{b/24-1e-6:.9f})' for a,b in ranges)
        nxt='ui'+str(index);parts.append(f"[{prior}][{index}:v]overlay=0:0:format=auto:enable='{condition}'[{nxt}]");prior=nxt
    parts.append(f'[{prior}]scale=out_color_matrix=bt709:out_range=tv:flags=accurate_rnd+full_chroma_int,format=yuv420p,setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709[v]')
    graph=';'.join(parts)
    run(['-safe','0','-r','24','-f','concat','-i',str(seq),*inputs,'-i',str(ROOT/'audio/mix_master.wav'),'-filter_complex',graph,'-map','[v]','-map',str(len(states)+1)+':a','-af',mastering,'-c:v','libx264','-preset','veryslow','-tune',tune,'-crf','10','-pix_fmt','yuv420p','-r','24','-frames:v',str(frame_limit),'-c:a','aac','-b:a','320k','-ar','48000','-t',str(frame_limit/24),'-movflags','+faststart',str(out)])
    print(str(out))
