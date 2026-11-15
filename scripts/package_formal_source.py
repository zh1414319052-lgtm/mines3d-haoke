"""Export the reviewed corresponding source without machine data or credentials."""
from pathlib import Path
import hashlib,json,shutil,zipfile,re,subprocess
ROOT=Path(__file__).resolve().parents[1]
PLATFORM=ROOT/'platform/haoke-game-platform'
OUT=ROOT/'build/formal-source'
ZIP=ROOT/'build/mines3d-1.7.1-haoke.2-source.zip'
SKIP={'.git','.gradle','build','__pycache__','renders','review','work','compressed-images','.pytest_cache','node_modules','.idea'}
DENY_NAMES={'local.properties','render_cache.json','render_progress.json','movie.ffconcat','intro_preview.ffconcat','reference.ffconcat'}
SCRIPTS={'build_launcher.ps1','sign_release.py','package_formal_source.py'}
DOCS={'docs/release/BUILD.md','docs/release/VERIFICATION.md','docs/release/package.json','docs/release/certificate.der','docs/release/apk-signature.txt','docs/online/ONLINE_SPEC.md'}
files={}
for p in ROOT.rglob('*'):
    if not p.is_file():continue
    rel=p.relative_to(ROOT);name=rel.as_posix()
    if any(part in SKIP for part in rel.parts) or p.name in DENY_NAMES:continue
    if p.suffix.lower() in {'.apk','.zip','.pyc','.blend1','.log','.ffconcat','.jks','.keystore','.p12','.dpapi'}:continue
    if rel.parts[0]=='docs' and name not in DOCS:continue
    if rel.parts[0]=='scripts' and p.name not in SCRIPTS:continue
    if p.suffix=='.mp4' and name!='art/mine_scene/sample.mp4':continue
    if rel.parts[0] not in {'app','gradle','art','docs','scripts','metadata','.github'} and len(rel.parts)>1:continue
    files[name]=p
for directory in ['backend','tests','frontend/src','frontend/public']:
    for p in (PLATFORM/directory).rglob('*'):
        rel=p.relative_to(PLATFORM)
        if p.is_file() and not any(x in SKIP for x in rel.parts):files['platform/haoke-game-platform/'+rel.as_posix()]=p
for name in ['requirements.txt','README.md','.env.example','frontend/package.json','frontend/package-lock.json','frontend/index.html','frontend/vite.config.js','scripts/deploy_mines_qa5.py','scripts/package_mines_deploy.py']:
    p=PLATFORM/name
    if p.is_file():files['platform/haoke-game-platform/'+name]=p
assert 'art/mine_scene/Mines3D_DeepSector.blend' in files and 'art/mine_scene/sample.mp4' in files
assert 'app/src/main/java/cos/premy/mines/online/PlatformApi.java' in files
assert 'platform/haoke-game-platform/backend/mines.py' in files
for name,p in files.items():
    assert p.name not in {'.env','fixtures.json','credentials.json'} and p.stat().st_size<95_000_000,name
    if p.suffix in {'.py','.java','.js','.jsx','.json','.md','.yml','.yaml','.properties','.txt','.xml'}:
        text=p.read_text('utf8',errors='replace')
        assert not re.search(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----)',text),name
        assert not re.search(r'eyJ[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{20,}',text),name
OUT.mkdir(parents=True,exist_ok=True)
for name,p in files.items():
    dest=OUT/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    # Preserve upstream CI byte-for-byte; this release does not modify workflows.
    if name.startswith('.github/'):
        dest.write_bytes(subprocess.check_output(['git','show','HEAD:'+name],cwd=ROOT))
manifest={name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in sorted(files)}
(OUT/'SOURCE_CONTENTS.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
with zipfile.ZipFile(ZIP,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for name in sorted(files):z.write(OUT/name,'Mines3D/'+name)
    z.write(OUT/'SOURCE_CONTENTS.json','Mines3D/SOURCE_CONTENTS.json')
with zipfile.ZipFile(ZIP) as z:assert z.testzip() is None
report={'files':len(files)+1,'sourceBytes':ZIP.stat().st_size,'sourceSha256':hashlib.sha256(ZIP.read_bytes()).hexdigest(),'sourceFile':str(ZIP),'export':str(OUT)}
(ROOT/'docs/release/source-package.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False))
