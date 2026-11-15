"""Assemble the authorized local QA APK and corresponding editable source, not a backup.
Retains upstream attribution and original assets. Excludes build caches, secrets and rendered frame caches.
"""
from pathlib import Path
import hashlib,json,shutil,zipfile
ART=Path(__file__).resolve().parents[1];ROOT=ART.parents[1];DELIVERY=ROOT.parent
APK=ROOT/'app/build/outputs/apk/debug/app-debug.apk'
APK_OUT=DELIVERY/'三维扫雷_矿井3D_1.7.1-QA.4_Android.apk'
ZIP_OUT=DELIVERY/'三维扫雷_矿井3D_QA.4_对应源码.zip'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
proof_names={
 'phase2-build.log','device-flows.log','device-levels-final.log','device-options.log','device-lifecycle.log','device-final-regression.json',
 'device-persistence.log','device-showcase-final.log','device-perf-final.log','phone-audio-check-final.json',
 'phone-blast-sync-final.jpg','phase2-verification.json','zipalign-qa4.log','signature-qa4.log','escape-levels.json',
 'escape-review-brief.txt','escape-review-result.txt','device-menu.jpg','english-board.jpg',
 'showcase-ready.png','showcase-flag.png','blast-dust.png','blast-settling.png','blast-result.png',
 'maximum-board.png','fault-0.png','fault-1.png','fault-2.png','landscape-restored.png','perf-final.png',
 'escape-0-ready.png','escape-1-ready.png','escape-2-ready.png','flat-fallback.png'
}
def included(p):
    rel=p.relative_to(ROOT);parts=rel.parts
    if any(x in {'.git','.gradle','.idea','build','__pycache__'} for x in parts):return False
    if p.name=='local.properties' or p.suffix.lower() in {'.apk','.jks','.keystore','.class','.pyc','.blend1'}:return False
    if rel.as_posix().startswith('art/mine_scene/renders/'):return False
    if rel.as_posix().startswith('art/mine_scene/review/'):return p.name in proof_names
    if rel.as_posix().startswith('art/mine_scene/mobile/level-tools/'):return False
    return True
assert APK.exists()
verification=json.loads((ART/'review/phase2-verification.json').read_text(encoding='utf-8-sig'))
assert verification['apk_sha256'].lower()==sha(APK)
assert verification['jvm_failures']==0 and verification['performance']['passed']
shutil.copyfile(APK,APK_OUT)
files=sorted(p for p in ROOT.rglob('*') if p.is_file() and included(p))
manifest=ART/'mobile/QA_MANIFEST.json'
files=[p for p in files if p!=manifest]
data={'edition':'Mines3D Deep Sector QA.4','application_id':'cos.premy.mines.qa','version_code':18,
      'apk_name':APK_OUT.name,'apk_sha256':sha(APK_OUT),'apk_bytes':APK_OUT.stat().st_size,
      'source_base':'Mines3D 1.7.1 / 535b3e547585aca7c10443fd0ce0ea84961ea7c5',
      'license':'GPL-3.0-only; bundled Noto fonts SIL OFL 1.1',
      'excluded':'Build/VCS caches, machine SDK path, signing keys, generated movie frame caches, temporary capture files.',
      'files':[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files]}
manifest.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8');files.append(manifest)
with zipfile.ZipFile(ZIP_OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in files:z.write(p,'源码/'+p.relative_to(ROOT).as_posix())
with zipfile.ZipFile(ZIP_OUT) as z:
    assert z.testzip() is None
    for name in ['app/src/main/assets/mine/scene.m3d','app/src/main/assets/mine/blast.wav','app/src/main/assets/mine/dust_atlas.png','art/mine_scene/Mines3D_DeepSector.blend','art/mine_scene/fonts/NotoSansSC-OFL.txt','app/src/main/java/cos/premy/mines/data/LogicSolver.java','gradle/wrapper/gradle-wrapper.jar','LICENSE']:
        assert '源码/'+name in z.namelist(),name
print(json.dumps({'apk':str(APK_OUT),'apk_sha256':sha(APK_OUT),'apk_bytes':APK_OUT.stat().st_size,'source_zip':str(ZIP_OUT),'source_zip_sha256':sha(ZIP_OUT),'source_zip_bytes':ZIP_OUT.stat().st_size,'source_files':len(files)},ensure_ascii=True,indent=2))
