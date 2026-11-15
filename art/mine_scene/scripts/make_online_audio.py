"""Original Mines3D multiplayer cues. No samples, synthesis only; GPL-3.0-only project assets.
48 kHz stereo, bounded peaks for phone speakers. Keep this source with exported WAVs.
"""
from pathlib import Path
import wave,json,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
DEST=ROOT/'app/src/main/assets/mine'
RATE=48000
def tone(t,f,decay=.24):return (np.sin(2*np.pi*f*t)+.16*np.sin(2*np.pi*f*2.01*t))*np.exp(-t/decay)*np.minimum(t/.004,1)
def delayed(n,start,sound):
    a=np.zeros(n);at=int(start*RATE);length=min(len(sound),n-at)
    if length>0:a[at:at+length]=sound[:length]
    return a
def render(name,duration,design):
    t=np.arange(int(duration*RATE))/RATE;n=len(t);rng=np.random.default_rng(71)
    if name=='start':
        # Mine lift relay catches, motor settles, paired warm bell.
        s=.16*rng.normal(size=n)*np.exp(-t*80)+.07*np.sin(2*np.pi*(92*t+30*t*t))*np.exp(-t*5)
        s+=.22*delayed(n,.18,tone(t,392,.25))+.2*delayed(n,.38,tone(t,587,.3))
    elif name=='turn':
        # Brief dry watch tick followed by a clear, higher notification.
        s=.07*rng.normal(size=n)*np.exp(-t*160)+.2*delayed(n,.085,tone(t,880,.11))
    elif name=='rescue':
        # A cable winch pulls continuously, three short ratchet teeth catch,
        # then one held consonant release signals a successful rescue.
        pull=np.minimum(t/.10,1)*np.maximum(0,1-t/.5)
        s=.19*np.sin(2*np.pi*(160*t+210*t*t))*pull
        for at in (.07,.13,.19):s+=.09*delayed(n,at,rng.normal(size=n)*np.exp(-t*170))
        s+=.18*delayed(n,.53,tone(t,440,.18)+.45*tone(t,660,.18))
    elif name=='eliminated':
        # Falling detuned warning, deliberately different from the explosion.
        phase=2*np.pi*(310*t-95*t*t);s=.22*np.sin(phase)*np.exp(-t*4)
        s+=.08*np.sin(phase*1.035)*np.exp(-t*5)
    elif name=='win':
        # Bright exit signal: rising arpeggio with a softly held major chord.
        s=sum(.14*delayed(n,k*.135,tone(t,f,.42)) for k,f in enumerate((392,494,587,784)))
    else:
        # Low, restrained failure cadence; no startling buzz or repeated explosion.
        s=.17*tone(t,294,.22)+.15*delayed(n,.22,tone(t,247,.23))+.18*delayed(n,.44,tone(t,196,.36))
    fade=np.minimum((duration-t)/.07,1);s*=np.maximum(0,fade);stereo=np.stack((s,s*.96),axis=1)
    data=(np.clip(stereo,-.8,.8)*32767).astype('<i2').tobytes();path=DEST/(name+'.wav')
    with wave.open(str(path),'wb') as out:out.setparams((2,2,RATE,len(t),'NONE','not compressed'));out.writeframes(data)
    return {'name':name,'duration':duration,'peak':float(np.abs(stereo).max()),'design':design,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
if __name__=='__main__':
    rows=[render(*args) for args in [('start',1.1,'lift relay + motor + paired bell'),('turn',.38,'tick + high chime'),('rescue',1.0,'continuous cable winch + ratchet + single release chord'),('eliminated',.7,'descending detuned warning'),('win',1.4,'exit arpeggio'),('lose',1.3,'low descending cadence')]]
    (ROOT/'art/mine_scene/ONLINE_AUDIO.json').write_text(json.dumps({'source':'Original procedural synthesis; no third-party samples','license':'GPL-3.0-only; commercial use permitted under project license','sample_rate':RATE,'cues':rows},indent=2),encoding='utf-8')
    print('Generated six distinct original multiplayer cues; peak bounded below 0.8.')
