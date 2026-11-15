"""After the sustained run, verify neighboring lifecycle paths on the frozen installed APK."""
from pathlib import Path
import subprocess,json,hashlib
from PIL import Image
ART=Path(__file__).resolve().parents[1];REVIEW=ART/'review';ROOT=ART.parents[1]
ADB=r'C:\Users\Administrator\AppData\Local\Android\Sdk\platform-tools\adb.exe'
BASE=[ADB,'-s','ee723f1e']
assert 'PASS perf' in (REVIEW/'device-perf-final.log').read_text(encoding='utf-8-sig')
def run(args):return subprocess.check_output(BASE+args,timeout=180)
apk=ROOT/'app/build/outputs/apk/debug/app-debug.apk';digest=hashlib.sha256(apk.read_bytes()).hexdigest()
path=run(['shell','pm','path','cos.premy.mines.qa']).decode().strip().removeprefix('package:')
assert run(['shell','sha256sum',path]).decode().split()[0]==digest
for suite in ['options','lifecycle','persistence']:
    output=run(['shell','am','instrument','-w','-e','suite',suite,'cos.premy.mines.qa/cos.premy.mines.graphics.DeviceChecks']).decode('utf8',errors='replace')
    (REVIEW/('device-'+suite+'.log')).write_text(output,encoding='utf8')
    assert 'PASS '+suite in output and 'FAIL ' not in output,output
    print('Final APK: PASS '+suite,flush=True)
for name in ['showcase-ready','showcase-flag','blast-dust','blast-settling','blast-result','maximum-board',
             'fault-0','fault-1','fault-2','escape-0-ready','escape-1-ready','escape-2-ready',
             'english-board','flat-fallback','landscape-restored','perf-final']:
    data=run(['exec-out','run-as','cos.premy.mines.qa','cat','files/qa/'+name+'.png'])
    assert data[:8]==b'\x89PNG\r\n\x1a\n',name
    target=REVIEW/(name+'.png');target.write_bytes(data)
    im=Image.open(target).convert('RGB');im.thumbnail((1024,1024));im.save(REVIEW/(name+'.jpg'),quality=83)
run(['shell','am','start','-n','cos.premy.mines.qa/cos.premy.mines.MainActivity'])
(REVIEW/'device-final-regression.json').write_text(json.dumps({'apk_sha256':digest,'installed_sha256':digest,
  'suites':['options','lifecycle','persistence'],'passed':True,'left_installed':True},indent=2),encoding='utf8')
print('Final APK installed hash matches; evidence pulled; QA main menu opened.',flush=True)
