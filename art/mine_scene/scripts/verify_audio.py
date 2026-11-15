"""Digital signal checks; explicitly not a physical speaker listening test."""
import json,wave
from pathlib import Path
import numpy as np
from scipy.signal import butter,sosfilt
ROOT=Path(__file__).resolve().parents[1]
def read(f):
    with wave.open(str(f)) as w:
        assert (w.getframerate(),w.getsampwidth(),w.getnchannels())==(48000,3,2)
        b=np.frombuffer(w.readframes(w.getnframes()),dtype=np.uint8).reshape(-1,3)
        q=b[:,0].astype(np.int32)|(b[:,1].astype(np.int32)<<8)|(b[:,2].astype(np.int32)<<16)
        q=(q^0x800000)-0x800000
        return q.reshape(-1,2)/8388607
a=read(ROOT/'audio/mix_master.wav');st=sum(read(f) for f in (ROOT/'audio/stems').glob('*.wav'))
mono=a.mean(axis=1);phone=sosfilt(butter(4,[250,5000],btype='bandpass',fs=48000,output='sos'),mono)
def rms(x):return float(20*np.log10(np.sqrt(np.mean(x*x))+1e-12))
result={'seconds':len(a)/48000,'sample_peak_dbfs':float(20*np.log10(np.max(np.abs(a)))),'stem_sum_max_error':float(np.max(np.abs(st-a))),'finite':bool(np.isfinite(a).all()),'phone_band_rms_dbfs':{'background':rms(phone[2*48000:4*48000]),'open':rms(phone[8*48000:int(8.32*48000)]),'flag':rms(phone[int(10.4*48000):int(10.78*48000)]),'blast_initial_320ms':rms(phone[14*48000:int(14.32*48000)])},'scope':'Digital signal checks and band-limited mono simulation; not physical phone listening'}
assert result['seconds']==24 and result['finite'] and result['sample_peak_dbfs']<-1.5 and result['stem_sum_max_error']<1e-6
assert min(result['phone_band_rms_dbfs'][k] for k in ['open','flag','blast_initial_320ms'])>result['phone_band_rms_dbfs']['background']+8
result['status']='PASS'
(ROOT/'review/audio-verification.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps(result))
