"""Create a reviewed deployment input from explicit source directories, no data/env."""
from pathlib import Path
import tarfile,hashlib,json,io
root=Path(__file__).resolve().parents[1]
out=root/'work/mines-deploy';out.mkdir(parents=True,exist_ok=True)
files=list((root/'backend').glob('*.py'))+list((root/'tests').glob('*.py'))+list((root/'frontend/dist').rglob('*'))
files += [root/'requirements.txt',root/'scripts/deploy_mines_qa5.py',root/'backend/api-docs.html']
files=[p for p in files if p.is_file()]
manifest={str(p.relative_to(root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
bundle=out/'mines3d-qa5-platform-v2.tar.gz'
with tarfile.open(bundle,'w:gz') as tar:
    for p in files:tar.add(p,arcname='mines3d-qa5-stage/'+str(p.relative_to(root)).replace('\\','/'))
    content=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('mines3d-qa5-stage/manifest.json');info.size=len(content);tar.addfile(info,io.BytesIO(content))
print(json.dumps({'path':str(bundle),'bytes':bundle.stat().st_size,'sha256':hashlib.sha256(bundle.read_bytes()).hexdigest(),'files':len(files)}))
