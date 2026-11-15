"""Run from the uploaded staging package, as root. No credentials or backups.
Preflight is read-only. Apply changes only the five Mines3D backend files and
the built public frontend. Existing data, .env, TLS and other downloads remain.
"""
import argparse,hashlib,json,os,shutil,sqlite3,subprocess,time,urllib.request
from pathlib import Path
STAGE=Path(__file__).resolve().parents[1]
APP=Path('/www/haoke-game-hub');WEB=Path('/www/wwwroot/cleanbizai.com');DATA=Path('/www/haoke-game-data/platform.sqlite3')
CHANGED=('app.py','rooms.py','admin.py','mines.py','mines_engine.py')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def preflight():
    assert APP.is_dir() and WEB.is_dir() and DATA.is_file()
    manifest=json.loads((STAGE/'manifest.json').read_text())
    for relative,expected in manifest.items():
        p=(STAGE/relative).resolve();assert p.is_relative_to(STAGE) and digest(p)==expected,relative
    with sqlite3.connect('file:'+str(DATA)+'?mode=ro',uri=True) as c:
        active=c.execute("SELECT count(*) FROM members m JOIN rooms r ON r.id=m.room_id WHERE r.status='playing' AND m.last_seen>?",(time.time()-45,)).fetchone()[0]
        before={'users':c.execute('SELECT count(*) FROM users').fetchone()[0],'profiles':c.execute('SELECT count(*) FROM profiles').fetchone()[0],
          'active_players':active,'migrations':[r[0] for r in c.execute('SELECT version FROM migrations ORDER BY version')]}
    print(json.dumps(before));assert active==0,'Live game players exist; do not interrupt their match'
    return before
def apply():
    before=preflight();envhash=digest(APP/'.env')
    for name in CHANGED:
        src=STAGE/'backend'/name;dest=APP/'backend'/name
        temp=dest.with_suffix('.mines-qa5-incoming');shutil.copyfile(src,temp);os.chmod(temp,0o644);os.replace(temp,dest)
    for src in (STAGE/'frontend/dist').rglob('*'):
        if not src.is_file():continue
        relative=src.relative_to(STAGE/'frontend/dist');dest=WEB/relative
        assert dest.resolve().is_relative_to(WEB)
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,dest);os.chmod(dest,0o644)
    subprocess.run(['systemctl','restart','haoke-game-hub'],check=True)
    for _ in range(20):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8768/api/health',timeout=2) as r:health=json.load(r)
            break
        except Exception:time.sleep(.5)
    else:raise RuntimeError('Service health did not return')
    assert health['version']=='0.5.0',health
    assert digest(APP/'.env')==envhash
    with sqlite3.connect('file:'+str(DATA)+'?mode=ro',uri=True) as c:
        assert c.execute('SELECT count(*) FROM users').fetchone()[0]==before['users']
        assert c.execute('SELECT count(*) FROM profiles').fetchone()[0]==before['profiles']
        assert c.execute('SELECT 1 FROM migrations WHERE version=7').fetchone()
    print(json.dumps({'deployed':'mines3d-qa.5','health':health,'existing_users_preserved':True,'env_unchanged':True}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['preflight','apply']);args=p.parse_args()
    (apply if args.action=='apply' else preflight)()
