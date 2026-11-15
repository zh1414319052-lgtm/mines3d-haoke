"""Validate and index the initial render after the in-session cache upgrade.
Only for this completed first render. Later render_movie runs maintain their own cache.
"""
import json,hashlib
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
complete=json.loads((ROOT/'render_complete.json').read_text());assert complete.get('finished')
ids=sorted(set(json.loads((ROOT/'frame_map.json').read_text()).values()))
cache={'source_sha':hashlib.sha256((ROOT/'Mines3D_DeepSector.blend').read_bytes()).hexdigest(),'renderer_sha':hashlib.sha256((ROOT/'scripts/render_movie.py').read_bytes()).hexdigest(),'frames':{}}
for f in ids:
    p=ROOT/'renders'/('%04d.png'%f)
    with Image.open(p) as image:
        assert image.size==(1080,1920);image.verify()
    cache['frames'][str(f)]=hashlib.sha256(p.read_bytes()).hexdigest()
(ROOT/'render_cache.json').write_text(json.dumps(cache,indent=2),encoding='utf8')
complete.update({k:cache[k] for k in ['source_sha','renderer_sha']})
(ROOT/'render_complete.json').write_text(json.dumps(complete,indent=2),encoding='utf8')
print('Validated and indexed',len(ids),'full-resolution PNGs. Source and renderer hashes recorded.')
