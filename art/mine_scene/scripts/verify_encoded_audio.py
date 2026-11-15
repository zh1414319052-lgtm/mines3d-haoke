"""Read-only comparison of delivered AAC timing against the original PCM mix.

Requires the final pipeline's metadata report, so an unrelated/older movie
cannot accidentally pass. Writes only the evidence JSON under review/.
This measures encoded timing; it is not a claim of physical speaker listening.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess

import numpy as np
from scipy import signal
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parents[1]
FF = Path(os.environ.get('FFMPEG_BIN', r'C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Packages\yt-dlp.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-N-124279-g0f6ba39122-win64-gpl\bin\ffmpeg.exe'))
metadata = json.loads((ROOT / 'review/video-verification.json').read_text(encoding='utf8'))
video = Path(metadata['video'])
video_sha = hashlib.sha256(video.read_bytes()).hexdigest().upper()
assert video_sha == metadata['sha256'], 'Video differs from the verified final encode'
rate, pcm = wavfile.read(ROOT / 'audio/mix_master.wav')
assert rate == 48000 and pcm.ndim == 2 and pcm.shape[1] == 2
source = pcm.astype(np.float64)
if np.issubdtype(pcm.dtype, np.integer):
    source /= max(abs(np.iinfo(pcm.dtype).min), np.iinfo(pcm.dtype).max)
decoded = subprocess.run(
    [str(FF), '-v', 'error', '-i', str(video), '-vn', '-map', '0:a:0',
     '-ac', '2', '-ar', str(rate), '-f', 'f32le', 'pipe:1'],
    capture_output=True, check=True,
)
audio = np.frombuffer(decoded.stdout, dtype='<f4').reshape(-1, 2)
assert np.isfinite(audio).all()
start, end = int(13.85 * rate), int(14.60 * rate)
assert len(audio) >= end
x = source[start:end].mean(axis=1)
y = audio[start:end].mean(axis=1).astype(np.float64)
x -= x.mean()
y -= y.mean()
correlation = signal.correlate(y, x, mode='full', method='fft')
lags = signal.correlation_lags(len(y), len(x), mode='full')
allowed = np.abs(lags) <= int(.25 * rate)
lag = int(lags[allowed][np.argmax(correlation[allowed])])
if lag > 0:
    x, y = x[:-lag], y[lag:]
elif lag < 0:
    x, y = x[-lag:], y[:lag]
similarity = float(np.dot(x, y) / np.sqrt(np.dot(x, x) * np.dot(y, y)))
assert abs(lag) <= rate / 24, f'Audio offset exceeds one video frame: {lag} samples'
assert similarity >= .85, f'Insufficient correlation to establish timing: {similarity}'
peak = float(np.max(np.abs(audio)))
assert peak < 1, f'Decoded audio reaches clipping: {peak}'
result = {
    'status': 'PASS', 'video_sha256': video_sha,
    'expected_flash_frame': 337, 'expected_flash_seconds': 14.0,
    'comparison_window_seconds': [13.85, 14.60],
    'encoded_audio_offset_samples': lag,
    'encoded_audio_offset_ms': lag / rate * 1000,
    'normalized_correlation': similarity,
    'decoded_sample_peak_dbfs': float(20 * np.log10(peak)),
    'decoded_audio_samples': len(audio), 'sample_rate': rate,
    'method': 'AAC decode cross-correlated with original PCM explosion window; visual flash checked in decoded frame 337',
    'not_tested': 'Physical phone speaker listening and Android runtime playback',
}
(ROOT / 'review/encoded-audio-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
print(json.dumps(result, ensure_ascii=False, indent=2))
