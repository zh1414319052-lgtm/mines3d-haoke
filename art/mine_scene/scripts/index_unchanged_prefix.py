"""One-time migration for the documented blast-only correction.
The initial geometry, lighting and camera through frame336 are unchanged.
Ignore every blast output and old noncanonical review frame. Never delete files.
"""
import hashlib,json
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
ids=sorted(set(json.loads((ROOT/'frame_map.json').read_text()).values()))
cache={'source_sha':hashlib.sha256((ROOT/'Mines3D_DeepSector.blend').read_bytes()).hexdigest(),'renderer_sha':hashlib.sha256((ROOT/'scripts/render_movie.py').read_bytes()).hexdigest(),'frames':{}}
for f in ids:
    p=ROOT/'renders'/('%04d.png'%f)
    if f>=337 or not p.exists():continue
    with Image.open(p) as im:
        assert im.size==(1080,1920);im.verify()
    cache['frames'][str(f)]=hashlib.sha256(p.read_bytes()).hexdigest()
(ROOT/'render_cache.json').write_text(json.dumps(cache,indent=2),encoding='utf8')
print('Indexed unchanged pre-blast PNGs:',len(cache['frames']))
