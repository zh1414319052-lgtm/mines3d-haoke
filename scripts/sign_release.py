"""Owner-authorized Windows signing. Secrets remain in DPAPI/external keystore only.
GPL-3.0-only. --create is exclusively for the first, explicitly approved identity.
"""
from pathlib import Path
import argparse, base64, ctypes, hashlib, json, os, subprocess
from ctypes import wintypes

ROOT=Path(__file__).resolve().parents[1]
APP='cos.premy.mines.haoke'; ALIAS='mines3d-haoke-release'
SIGNROOT=Path(os.environ['LOCALAPPDATA'])/'Haoke/AndroidSigning'
IDENTITY=SIGNROOT/'mines3d-release'
SDK=Path(os.environ['ANDROID_HOME'])/'build-tools/36.0.0'
KEYTOOL=Path(os.environ['JAVA_HOME'])/'bin/keytool.exe'
OUTPUT=ROOT.parent/'三维扫雷_矿井联机_1.7.1-haoke.2_Android.apk'

def run(args,env=None):
    p=subprocess.run([str(x) for x in args],env=env,cwd=ROOT,capture_output=True,timeout=120)
    if p.returncode: raise RuntimeError('Signing step failed: '+Path(str(args[0])).name)
    return p.stdout
def sha(raw): return hashlib.sha256(raw).hexdigest()
def unseal(path):
    class Blob(ctypes.Structure): _fields_=[('n',wintypes.DWORD),('p',ctypes.POINTER(ctypes.c_ubyte))]
    raw=base64.b64decode(path.read_bytes(),validate=True)
    buf=(ctypes.c_ubyte*len(raw)).from_buffer_copy(raw); a=Blob(len(raw),buf); b=Blob()
    dll=ctypes.WinDLL('crypt32',use_last_error=True)
    if not dll.CryptUnprotectData(ctypes.byref(a),None,None,None,None,1,ctypes.byref(b)):
        raise RuntimeError('Protected signing password unavailable')
    kernel=ctypes.WinDLL('kernel32');kernel.LocalFree.argtypes=[ctypes.c_void_p]
    try:return json.loads(ctypes.string_at(b.p,b.n))
    finally:kernel.LocalFree(b.p)
def certificate(store,alias,env):
    return run([KEYTOOL,'-exportcert','-keystore',store,'-alias',alias,'-storepass:env','MINES_STORE_PASS'],env)
def write(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
def main(create=False):
    shared=SIGNROOT/'shared-release-password'
    ref=json.loads((shared/'credential-reference.json').read_text('utf8'))
    values=unseal(shared/'credentials.dpapi')
    env={**os.environ,'MINES_STORE_PASS':values['store_pass'],'MINES_KEY_PASS':values['key_pass']}
    try:
        if create:
            if IDENTITY.exists():raise RuntimeError('Identity already exists; refusing replacement')
            source=Path.home()/'.haoke/AndroidSigning/anxreader-release'
            meta=json.loads((source/'signing-identity.json').read_text('utf8'))
            assert meta['applicationId']==ref['source_application'] and meta['alias']==ref['source_alias']
            assert sha(certificate(source/meta['keystoreFile'],meta['alias'],env))==ref['source_certificate_sha256'].lower()
            assert values['store_pass']==values['key_pass']
            IDENTITY.mkdir(exist_ok=False)
            run(['icacls.exe',IDENTITY,'/inheritance:r','/grant:r',os.environ['USERNAME']+':(OI)(CI)F','*S-1-5-18:(OI)(CI)F'])
            store=IDENTITY/'mines3d-haoke-release.p12'
            run([KEYTOOL,'-genkeypair','-keystore',store,'-storetype','PKCS12','-alias',ALIAS,
                '-keyalg','RSA','-keysize','4096','-validity','18250','-dname','CN=Haoke Mines3D, O=Haoke',
                '-storepass:env','MINES_STORE_PASS','-keypass:env','MINES_KEY_PASS'],env)
            der=certificate(store,ALIAS,env)
            write(IDENTITY/'signing-identity.json',{'applicationId':APP,'alias':ALIAS,'keystoreFile':store.name,
                'certificateSha256':sha(der),'storeType':'PKCS12','keyAlgorithm':'RSA-4096',
                'passwordReference':'../shared-release-password/credentials.dpapi',
                'creationAuthorization':'User explicitly approved independent Mines3D identity on 2026-11-15'})
            (IDENTITY/'certificate.der').write_bytes(der)
        meta=json.loads((IDENTITY/'signing-identity.json').read_text('utf8'))
        assert meta['applicationId']==APP and meta['alias']==ALIAS
        store=IDENTITY/meta['keystoreFile']
        assert store.resolve().parent==IDENTITY.resolve()
        der=certificate(store,ALIAS,env);assert sha(der)==meta['certificateSha256']
        # aapt/zipalign on Windows cannot reliably open non-ASCII absolute paths.
        unsigned=Path('app/build/outputs/apk/release/app-release-unsigned.apk')
        badging=run([SDK/'aapt.exe','dump','badging',unsigned]).decode('utf8')
        assert "package: name='cos.premy.mines.haoke' versionCode='21' versionName='1.7.1-haoke.2'" in badging
        assert 'application-debuggable' not in badging
        run([SDK/'zipalign.exe','-c','-P','16','4',unsigned])
        run([SDK/'apksigner.bat','sign','--ks',store,'--ks-key-alias',ALIAS,'--ks-pass','env:MINES_STORE_PASS',
            '--key-pass','env:MINES_KEY_PASS','--v1-signing-enabled','true','--v2-signing-enabled','true',
            '--v3-signing-enabled','true','--v4-signing-enabled','false','--out',OUTPUT,unsigned],env)
        verified=run([SDK/'apksigner.bat','verify','--verbose','--print-certs',OUTPUT]).decode('utf8')
        assert meta['certificateSha256'] in verified.lower()
        result={'version':'1.7.1-haoke.2','versionCode':21,'applicationId':APP,'certificateSha256':sha(der),
            'bytes':OUTPUT.stat().st_size,'apkSha256':sha(OUTPUT.read_bytes()),'debuggable':False,'minSdk':19}
        write(ROOT/'docs/release/package.json',result)
        (ROOT/'docs/release/apk-signature.txt').write_text(verified,encoding='utf8')
        (ROOT/'docs/release/certificate.der').write_bytes(der)
        print(json.dumps(result))
    finally:
        values.clear();env.pop('MINES_STORE_PASS',None);env.pop('MINES_KEY_PASS',None)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--create',action='store_true');args=parser.parse_args();main(args.create)
