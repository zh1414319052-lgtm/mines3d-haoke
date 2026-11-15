"""Mines3D authenticated, server-authoritative adapter. Existing platform identities/rooms.

State synchronization uses bounded foreground HTTPS polling (800ms), not the Liquid Wars
byte relay. Every mutation is a SQLite write transaction; restart keeps matches intact.
"""
import asyncio
import hashlib
import json
import secrets
import time
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, Request
from pydantic import Field, field_validator
from .db import allrows, rowdict
from .models import StrictModel
from .security import user_required, fail
from . import mines_engine as engine

GAME='mines3d'
PROTOCOL=1
BUILD=19
router=APIRouter(prefix='/api/mines',tags=['Mines3D authoritative multiplayer'])
SCHEMA='''
CREATE TABLE IF NOT EXISTS mines_rooms(room_id TEXT PRIMARY KEY REFERENCES rooms(id),settings TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,match_id TEXT);
CREATE TABLE IF NOT EXISTS mines_people(room_id TEXT NOT NULL REFERENCES rooms(id),user_id TEXT NOT NULL REFERENCES users(id),role TEXT NOT NULL DEFAULT 'miner',observer INTEGER NOT NULL DEFAULT 0,last_seen REAL NOT NULL,PRIMARY KEY(room_id,user_id));
CREATE TABLE IF NOT EXISTS mines_matches(id TEXT PRIMARY KEY,room_id TEXT NOT NULL REFERENCES rooms(id),state TEXT NOT NULL,created_at REAL NOT NULL,ended_at REAL,result TEXT);
CREATE INDEX IF NOT EXISTS mines_matches_room ON mines_matches(room_id,created_at);
CREATE TABLE IF NOT EXISTS mines_commands(match_id TEXT NOT NULL REFERENCES mines_matches(id),user_id TEXT NOT NULL,command_id TEXT NOT NULL,fingerprint TEXT NOT NULL,applied_version INTEGER NOT NULL,PRIMARY KEY(match_id,user_id,command_id));
CREATE TABLE IF NOT EXISTS mines_queue(user_id TEXT PRIMARY KEY REFERENCES users(id),settings TEXT NOT NULL,role TEXT NOT NULL,protocol INTEGER NOT NULL,joined_at REAL NOT NULL,last_seen REAL NOT NULL);
CREATE TABLE IF NOT EXISTS mines_results(match_id TEXT NOT NULL REFERENCES mines_matches(id),user_id TEXT NOT NULL,mode TEXT NOT NULL,day TEXT NOT NULL,players INTEGER NOT NULL,difficulty INTEGER NOT NULL,rule_version INTEGER NOT NULL,elapsed REAL NOT NULL,won INTEGER NOT NULL,score INTEGER NOT NULL,contribution TEXT NOT NULL,PRIMARY KEY(match_id,user_id));
CREATE TABLE IF NOT EXISTS mines_test_users(user_id TEXT PRIMARY KEY REFERENCES users(id));
'''


class Settings(StrictModel):
    mode:Literal['coop','hunt','puzzle','fault','daily','race','team']='coop'
    difficulty:int=Field(default=0,ge=0,le=1)
    map:int=Field(default=0,ge=0,le=3)
    size:Literal[5,8,10,12,15]=5
    layers:int=Field(default=0,ge=0,le=8)
    @field_validator('layers')
    @classmethod
    def valid_layers(cls,value):
        if value==1:raise ValueError('Use automatic or 2–8 decks')
        return value


class Hello(StrictModel):
    protocol:int
    build:int


class Create(StrictModel):
    settings:Settings=Field(default_factory=Settings)
    role:Literal['miner','scout','medic']='miner'


class Join(StrictModel):
    role:Literal['miner','scout','medic']='miner'


class Ready(StrictModel):
    ready:bool
    revision:int


class Configure(Create):
    revision:int


class Start(StrictModel):
    revision:int


class Sync(StrictModel):
    watch:str|None=Field(default=None,max_length=64)


class Command(StrictModel):
    match_id:str=Field(min_length=16,max_length=64)
    command_id:str=Field(min_length=16,max_length=64,pattern=r'^[a-zA-Z0-9_-]+$')
    version:int=Field(ge=1)
    action:Literal['open','flag','confirm','scan','rescue','danger','safe','help','hint']
    cell:int|None=Field(default=None,ge=0,le=1799)
    target:str|None=Field(default=None,max_length=64)


def dump(data):return json.dumps(data,separators=(',',':'),ensure_ascii=False)


def initialize(conn,now):
    conn.executescript(SCHEMA)
    if 'settings' not in [c[1] for c in conn.execute('PRAGMA table_info(mines_results)')]:
        conn.execute("ALTER TABLE mines_results ADD COLUMN settings TEXT NOT NULL DEFAULT '{}'")
    # Registration is restricted to this new game. No existing identity/config is rewritten.
    conn.execute("INSERT OR IGNORE INTO games VALUES(?,?,?,?,?,?,'visible',6,2,'server-authoritative',?)",
                 (GAME,GAME,'三维扫雷 · 矿井联机','2–6 人合作探矿与猎雷淘汰赛','立体矿井、共享线索、服务器判定。Android 联网 QA。','3D cooperative puzzle',now))
    conn.execute('INSERT OR IGNORE INTO migrations VALUES(7,?)',(now,))


def admitted(request:Request,p=Depends(user_required)):
    if not request.headers.get('authorization','').startswith('Bearer '):fail(403,'NATIVE_REQUIRED','请在游戏中操作 / Use the game client')
    with request.app.state.db.connect() as conn:
        row=conn.execute('SELECT * FROM native_clients WHERE user_id=? AND game_id=?',(p.user['id'],GAME)).fetchone()
    if not row or row['session_hash']!=p.session_hash or row['protocol']!=PROTOCOL or row['build']<BUILD:
        fail(409,'UPDATE_REQUIRED','请重新登录或更新游戏 / Sign in again or update')
    return p


def get_room(conn,code):
    row=conn.execute('SELECT * FROM rooms WHERE code=? AND game_id=?',(code.upper(),GAME)).fetchone()
    if not row:fail(404,'ROOM_NOT_FOUND','房间不存在 / Room not found')
    if row['status']=='closed':fail(410,'ROOM_CLOSED','房间已关闭 / Room is closed')
    return dict(row)


def state_row(conn,room):
    return conn.execute('SELECT * FROM mines_rooms WHERE room_id=?',(room['id'],)).fetchone()


def member(conn,room,uid,playing=True):
    row=conn.execute('SELECT * FROM mines_people WHERE room_id=? AND user_id=?',(room['id'],uid)).fetchone()
    if not row or (playing and row['observer']):fail(403,'NOT_A_MEMBER','你不是参赛成员 / Player membership required')
    return row


def active_room(conn,uid):
    return conn.execute("SELECT r.* FROM members m JOIN rooms r ON r.id=m.room_id WHERE m.user_id=? AND m.game_id=? AND r.status IN ('waiting','playing','finished')",(uid,GAME)).fetchone()


def room_view(conn,room,now):
    config=state_row(conn,room)
    people=allrows(conn,'''SELECT m.user_id AS id,u.nickname AS name,u.avatar,m.ready,m.last_seen,p.role
       FROM members m JOIN users u ON u.id=m.user_id JOIN mines_people p ON p.room_id=m.room_id AND p.user_id=m.user_id
       WHERE m.room_id=? ORDER BY m.joined_at,m.user_id''',(room['id'],))
    for p in people:p['ready']=bool(p['ready']);p['online']=now-p.pop('last_seen')<10
    watchers=conn.execute('SELECT count(*) FROM mines_people WHERE room_id=? AND observer=1',(room['id'],)).fetchone()[0]
    return {'code':room['code'],'host':room['host_id'],'status':room['status'],'revision':config['revision'],
            'settings':json.loads(config['settings']),'match_id':config['match_id'],'players':people,'spectators':watchers,
            'max_players':6,'min_players':6 if json.loads(config['settings'])['mode']=='team' else 2}


def create(conn,user,settings,role,now):
    from .rooms import enter_game
    existing=active_room(conn,user['id'])
    if existing:return dict(existing)
    conn.execute('DELETE FROM mines_queue WHERE user_id=?',(user['id'],))
    rid=uuid.uuid4().hex
    for _ in range(10):
        code=''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6))
        if not conn.execute('SELECT 1 FROM rooms WHERE code=?',(code,)).fetchone():break
    else:fail(503,'CODE_ALLOCATION_FAILED','请稍后重试 / Try again')
    conn.execute("INSERT INTO rooms VALUES(?,?,?,?,'waiting',?,?,?)",(rid,code,GAME,user['id'],now,now,now+86400))
    conn.execute('INSERT INTO mines_rooms VALUES(?,?,1,NULL)',(rid,dump(settings)))
    conn.execute('INSERT INTO members VALUES(?,?,?,0,?,?)',(rid,user['id'],GAME,now,now))
    conn.execute('INSERT INTO mines_people VALUES(?,?,?,0,?)',(rid,user['id'],role,now))
    enter_game(conn,user,GAME)
    return get_room(conn,code)


def join(conn,room,user,role,now):
    from .rooms import enter_game
    require_waiting(room)
    other=active_room(conn,user['id'])
    if other and other['id']!=room['id']:fail(409,'ALREADY_IN_ROOM','请先退出原房间 / Leave your current room first')
    current=conn.execute('SELECT 1 FROM members WHERE room_id=? AND user_id=?',(room['id'],user['id'])).fetchone()
    if not current:
        if conn.execute('SELECT count(*) FROM members WHERE room_id=?',(room['id'],)).fetchone()[0]>=6:fail(409,'ROOM_FULL','房间已满 / Room is full')
        conn.execute('INSERT INTO members VALUES(?,?,?,0,?,?)',(room['id'],user['id'],GAME,now,now))
        conn.execute('INSERT INTO mines_people VALUES(?,?,?,0,?) ON CONFLICT(room_id,user_id) DO UPDATE SET role=excluded.role,observer=0,last_seen=excluded.last_seen',(room['id'],user['id'],role,now))
    conn.execute('DELETE FROM mines_queue WHERE user_id=?',(user['id'],));enter_game(conn,user,GAME)


def require_waiting(room):
    if room['status']!='waiting' or room['expires_at']<time.time():fail(409,'ROOM_NOT_WAITING','房间已开局或失效 / Room is no longer waiting')


def load_match(conn,room):
    config=state_row(conn,room)
    if not config or not config['match_id']:return None
    row=conn.execute('SELECT state FROM mines_matches WHERE id=?',(config['match_id'],)).fetchone()
    return json.loads(row['state']) if row else None


def save_match(conn,room,match):
    conn.execute('UPDATE mines_matches SET state=?,ended_at=?,result=? WHERE id=?',(dump(match),match['ended'],dump({'winners':match['winners'],'reason':match['reason']}) if match['ended'] is not None else None,match['id']))
    for p in match['players']:
        if p['left']:
            conn.execute('DELETE FROM members WHERE room_id=? AND user_id=?',(room['id'],p['id']))
            conn.execute('UPDATE mines_people SET observer=1 WHERE room_id=? AND user_id=?',(room['id'],p['id']))
    remaining=conn.execute('SELECT user_id FROM members WHERE room_id=? ORDER BY joined_at,user_id',(room['id'],)).fetchall()
    if remaining and room['host_id'] not in [r[0] for r in remaining]:
        conn.execute('UPDATE rooms SET host_id=? WHERE id=?',(remaining[0][0],room['id']))
    if match['ended'] is None:return
    conn.execute("UPDATE rooms SET status='finished',updated_at=? WHERE id=? AND status='playing'",(match['ended'],room['id']))
    for p in match['players']:
        if conn.execute('SELECT 1 FROM mines_test_users WHERE user_id=?',(p['id'],)).fetchone():continue
        conn.execute('INSERT OR IGNORE INTO mines_results VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                     (match['id'],p['id'],match['mode'],match['day'],match['initial_players'],match['settings']['difficulty'],engine.VERSION,
                      match['ended']-match['created'],int(p['id'] in match['winners']),p['score'],dump({k:p.get(k,0) for k in ('opened','route_cells','rescues','assists','hints')}),dump(match['settings'])))


def remove_member(conn,room,uid,now):
    """Called by common account revocation and timeout paths as well as explicit leave."""
    match=load_match(conn,room)
    if match and match['ended'] is None:engine.leave(match,uid,now);save_match(conn,room,match)
    conn.execute('DELETE FROM members WHERE room_id=? AND user_id=?',(room['id'],uid))
    conn.execute('DELETE FROM mines_people WHERE room_id=? AND user_id=?',(room['id'],uid))
    remaining=conn.execute('SELECT user_id FROM members WHERE room_id=? ORDER BY joined_at,user_id',(room['id'],)).fetchall()
    if not remaining:conn.execute("UPDATE rooms SET status='closed',updated_at=? WHERE id=?",(now,room['id']))
    elif room['host_id']==uid:conn.execute('UPDATE rooms SET host_id=?,updated_at=? WHERE id=?',(remaining[0]['user_id'],now,room['id']))


@router.post('/enter')
def enter(body:Hello,request:Request,p=Depends(user_required)):
    if body.protocol!=PROTOCOL or body.build<BUILD:fail(409,'UPDATE_REQUIRED','请更新游戏 / Update required')
    if not request.headers.get('authorization','').startswith('Bearer '):fail(403,'NATIVE_REQUIRED','需要游戏会话 / Native session required')
    from .rooms import enter_game,get_game
    with request.app.state.db.connect(write=True) as conn:
        get_game(conn,GAME);enter_game(conn,p.user,GAME)
        conn.execute('INSERT INTO native_clients VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,game_id) DO UPDATE SET session_hash=excluded.session_hash,protocol=excluded.protocol,build=excluded.build,last_seen=excluded.last_seen',(p.user['id'],GAME,p.session_hash,PROTOCOL,body.build,time.time()))
    return {'game_id':GAME,'protocol':PROTOCOL,'modes':engine.MODES,'user_id':p.user['id']}


@router.get('/rooms')
def list_rooms(request:Request,p=Depends(admitted)):
    with request.app.state.db.connect() as conn:
        current=active_room(conn,p.user['id']);now=time.time()
        rows=allrows(conn,"SELECT * FROM rooms WHERE game_id=? AND status IN ('waiting','playing') AND expires_at>? ORDER BY created_at DESC LIMIT 50",(GAME,now))
        return {'rooms':[room_view(conn,r,now) for r in rows], 'current':current['code'] if current else None}


@router.post('/rooms')
def create_room(body:Create,request:Request,p=Depends(admitted)):
    with request.app.state.db.connect(write=True) as conn:
        room=create(conn,p.user,body.settings.model_dump(),body.role,time.time())
        return {'room':room_view(conn,room,time.time())}


@router.post('/rooms/{code}/join')
def join_room(code:str,body:Join,request:Request,p=Depends(admitted)):
    with request.app.state.db.connect(write=True) as conn:
        room=get_room(conn,code);join(conn,room,p.user,body.role,time.time())
        return {'room':room_view(conn,room,time.time())}


@router.post('/rooms/{code}/watch')
def watch_room(code:str,request:Request,p=Depends(admitted)):
    with request.app.state.db.connect(write=True) as conn:
        room=get_room(conn,code)
        if room['status'] not in ('playing','finished'):fail(409,'NO_MATCH','尚未开局 / Match has not started')
        existing=conn.execute('SELECT 1 FROM mines_people WHERE room_id=? AND user_id=?',(room['id'],p.user['id'])).fetchone()
        if not existing:
            if conn.execute('SELECT count(*) FROM mines_people WHERE room_id=? AND observer=1',(room['id'],)).fetchone()[0]>=24:fail(409,'SPECTATORS_FULL','观战席已满 / Spectators full')
            conn.execute("INSERT INTO mines_people VALUES(?,?,'miner',1,?)",(room['id'],p.user['id'],time.time()))
        return {'room':room_view(conn,room,time.time())}


@router.post('/rooms/{code}/configure')
def configure(code:str,body:Configure,request:Request,p=Depends(admitted)):
    with request.app.state.db.connect(write=True) as conn:
        room=get_room(conn,code);require_waiting(room);member(conn,room,p.user['id'])
        if room['host_id']!=p.user['id']:fail(403,'HOST_REQUIRED','仅房主可修改 / Host only')
        if state_row(conn,room)['revision']!=body.revision:fail(409,'ROOM_CHANGED','设置已改变 / Settings changed')
        conn.execute('UPDATE mines_rooms SET settings=?,revision=revision+1 WHERE room_id=?',(dump(body.settings.model_dump()),room['id']))
        conn.execute('UPDATE members SET ready=0 WHERE room_id=?',(room['id'],))
        conn.execute('UPDATE mines_people SET role=? WHERE room_id=? AND user_id=?',(body.role,room['id'],p.user['id']))
        return {'room':room_view(conn,room,time.time())}


@router.post('/rooms/{code}/role')
def set_role(code:str,body:Join,request:Request,p=Depends(admitted)):
    with request.app.state.db.connect(write=True) as conn:
        room=get_room(conn,code);require_waiting(room);member(conn,room,p.user['id'])
        conn.execute('UPDATE mines_people SET role=? WHERE room_id=? AND user_id=?',(body.role,room['id'],p.user['id']))
        conn.execute('UPDATE members SET ready=0 WHERE room_id=? AND user_id=?',(room['id'],p.user['id']))
    return {'ok':True}


@router.post('/rooms/{code}/ready')
def ready(code:str,body:Ready,request:Request,p=Depends(admitted)):
    with request.app.state.db.connect(write=True) as conn:
        room=get_room(conn,code);require_waiting(room);member(conn,room,p.user['id'])
        if state_row(conn,room)['revision']!=body.revision:fail(409,'ROOM_CHANGED','请确认新的设置 / Review changed settings')
        conn.execute('UPDATE members SET ready=?,last_seen=? WHERE room_id=? AND user_id=?',(int(body.ready),time.time(),room['id'],p.user['id']))
    return {'ok':True}


@router.post('/rooms/{code}/start')
def start(code:str,body:Start,request:Request,p=Depends(admitted)):
    with request.app.state.db.connect(write=True) as conn:
        room=get_room(conn,code);member(conn,room,p.user['id'])
        if room['host_id']!=p.user['id']:fail(403,'HOST_REQUIRED','仅房主可开始 / Host only')
        if room['status']=='playing':return {'match_id':state_row(conn,room)['match_id']}
        require_waiting(room);config=state_row(conn,room)
        if config['revision']!=body.revision:fail(409,'ROOM_CHANGED','设置已改变 / Settings changed')
        people=room_view(conn,room,time.time())['players']
        minimum=6 if json.loads(config['settings'])['mode']=='team' else 2
        if len(people)<minimum:fail(409,'NOT_ENOUGH_PLAYERS','人数不足 / Not enough players')
        if any(not p['ready'] or not p['online'] for p in people):fail(409,'NOT_READY','请等待全部玩家准备 / All players must be ready and online')
        match=engine.new_match(json.loads(config['settings']),people,uuid.uuid4().hex,time.time(),request.app.state.config.secret)
        conn.execute('INSERT INTO mines_matches VALUES(?,?,?,?,NULL,NULL)',(match['id'],room['id'],dump(match),match['created']))
        conn.execute('UPDATE mines_rooms SET match_id=? WHERE room_id=?',(match['id'],room['id']))
        conn.execute("UPDATE rooms SET status='playing',updated_at=? WHERE id=?",(match['created'],room['id']))
        return {'match_id':match['id']}


@router.post('/rooms/{code}/sync')
def sync(code:str,body:Sync,request:Request,p=Depends(admitted)):
    now=time.time()
    with request.app.state.db.connect(write=True) as conn:
        room=get_room(conn,code);who=member(conn,room,p.user['id'],False)
        match=load_match(conn,room)
        # Tick before refreshing last_seen so an expired player cannot resurrect by polling.
        if match:
            engine.tick(match,now)
            player=next((x for x in match['players'] if x['id']==p.user['id']),None)
            if player and not player['left']:player['seen']=now
            save_match(conn,room,match)
        conn.execute('UPDATE mines_people SET last_seen=? WHERE room_id=? AND user_id=?',(now,room['id'],p.user['id']))
        conn.execute('UPDATE members SET last_seen=? WHERE room_id=? AND user_id=?',(now,room['id'],p.user['id']))
        room=get_room(conn,code)
        return {'room':room_view(conn,room,now),'match':engine.project(match,p.user['id'],now,body.watch) if match else None,'observer':bool(who['observer'])}


@router.post('/rooms/{code}/command')
def command(code:str,body:Command,request:Request,p=Depends(admitted)):
    now=time.time();error=None;duplicate=False
    fingerprint=hashlib.sha256(dump(body.model_dump()).encode()).hexdigest()
    with request.app.state.db.connect(write=True) as conn:
        room=get_room(conn,code);member(conn,room,p.user['id']);match=load_match(conn,room)
        if not match or body.match_id!=match['id']:fail(409,'STALE_MATCH','这是旧对局操作 / Old match command')
        # Commands prove activity too. Expire first, so late/replayed commands never
        # resurrect a departed player; keep heartbeats even on stale state errors.
        engine.tick(match,now)
        player=next((x for x in match['players'] if x['id']==p.user['id']),None)
        if player and not player['left']:player['seen']=now
        conn.execute('UPDATE mines_people SET last_seen=? WHERE room_id=? AND user_id=?',(now,room['id'],p.user['id']))
        conn.execute('UPDATE members SET last_seen=? WHERE room_id=? AND user_id=?',(now,room['id'],p.user['id']))
        cached=conn.execute('SELECT * FROM mines_commands WHERE match_id=? AND user_id=? AND command_id=?',(match['id'],p.user['id'],body.command_id)).fetchone()
        if cached:
            if cached['fingerprint']!=fingerprint:fail(409,'COMMAND_REUSED','命令编号已用于其他操作 / Command ID reused')
            duplicate=True
        else:
            if body.version!=match['version']:error='STATE_CHANGED'
            else:
                try:engine.apply(match,p.user['id'],body.action,body.cell,body.target,now)
                except engine.RuleError as ex:error=ex.code
                else:conn.execute('INSERT INTO mines_commands VALUES(?,?,?,?,?)',(match['id'],p.user['id'],body.command_id,fingerprint,match['version']))
        save_match(conn,room,match)
        result={'match':engine.project(match,p.user['id'],now),'duplicate':duplicate}
    if error:fail(409,error,'操作未执行，请查看当前局面 / Action not applied; check the current state')
    return result


@router.post('/rooms/{code}/leave')
def leave(code:str,request:Request,p=Depends(admitted)):
    with request.app.state.db.connect(write=True) as conn:
        room=get_room(conn,code);member(conn,room,p.user['id'],False)
        remove_member(conn,room,p.user['id'],time.time())
    return {'ok':True}


@router.post('/rooms/{code}/again')
def again(code:str,body:Start,request:Request,p=Depends(admitted)):
    with request.app.state.db.connect(write=True) as conn:
        room=get_room(conn,code);member(conn,room,p.user['id'])
        if room['host_id']!=p.user['id']:fail(403,'HOST_REQUIRED','仅房主可重新组局 / Host only')
        if room['status']=='waiting':return {'ok':True}
        if room['status']!='finished':fail(409,'MATCH_NOT_FINISHED','对局尚未结束 / Match is not finished')
        if state_row(conn,room)['revision']!=body.revision:fail(409,'ROOM_CHANGED','房间已改变 / Room changed')
        conn.execute("UPDATE rooms SET status='waiting',expires_at=?,updated_at=? WHERE id=?",(time.time()+86400,time.time(),room['id']))
        conn.execute('UPDATE mines_rooms SET match_id=NULL,revision=revision+1 WHERE room_id=?',(room['id'],))
        conn.execute('UPDATE members SET ready=0 WHERE room_id=?',(room['id'],))
    return {'ok':True}


@router.post('/matchmaking/enqueue')
def enqueue(body:Create,request:Request,p=Depends(admitted)):
    with request.app.state.db.connect(write=True) as conn:
        current=active_room(conn,p.user['id'])
        if current:return {'room':room_view(conn,dict(current),time.time())}
        now=time.time();settings=dump(body.settings.model_dump())
        conn.execute('INSERT INTO mines_queue VALUES(?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET settings=excluded.settings,role=excluded.role,protocol=excluded.protocol,last_seen=excluded.last_seen',(p.user['id'],settings,body.role,PROTOCOL,now,now))
    return {'queued':True}


@router.post('/matchmaking/poll')
def poll_queue(request:Request,p=Depends(admitted)):
    now=time.time()
    with request.app.state.db.connect(write=True) as conn:
        current=active_room(conn,p.user['id'])
        if current:return {'room':room_view(conn,dict(current),now)}
        conn.execute('DELETE FROM mines_queue WHERE last_seen<?',(now-40,))
        conn.execute('UPDATE mines_queue SET last_seen=? WHERE user_id=?',(now,p.user['id']))
        q=conn.execute('SELECT * FROM mines_queue WHERE user_id=?',(p.user['id'],)).fetchone()
        if not q:return {'queued':False}
        group=allrows(conn,'SELECT * FROM mines_queue WHERE settings=? AND protocol=? ORDER BY joined_at,user_id LIMIT 6',(q['settings'],PROTOCOL))
        settings=json.loads(q['settings']);minimum=6 if settings['mode']=='team' else 2
        if len(group)<minimum:return {'queued':True,'waiting':len(group),'minimum':minimum}
        host=dict(conn.execute('SELECT * FROM users WHERE id=?',(group[0]['user_id'],)).fetchone())
        room=create(conn,host,settings,group[0]['role'],now)
        for item in group[1:]:
            user=dict(conn.execute('SELECT * FROM users WHERE id=?',(item['user_id'],)).fetchone())
            join(conn,room,user,item['role'],now)
        current=active_room(conn,p.user['id'])
        return {'room':room_view(conn,dict(current),now)} if current else {'queued':True}


@router.post('/matchmaking/cancel')
def cancel_queue(request:Request,p=Depends(admitted)):
    with request.app.state.db.connect(write=True) as conn:
        conn.execute('DELETE FROM mines_queue WHERE user_id=?',(p.user['id'],))
        current=active_room(conn,p.user['id'])
        return {'room':room_view(conn,dict(current),time.time())} if current else {'queued':False}


@router.get('/records')
def records(request:Request,p=Depends(admitted)):
    with request.app.state.db.connect() as conn:
        rows=allrows(conn,'SELECT mode,day,players,difficulty,rule_version,elapsed,won,score,contribution,settings FROM mines_results WHERE user_id=? ORDER BY rowid DESC LIMIT 30',(p.user['id'],))
        for r in rows:r['settings']=json.loads(r['settings']);r['contribution']=json.loads(r['contribution'])
    return {'records':rows}


def sweep_once(app):
    now=time.time()
    with app.state.db.connect(write=True) as conn:
        for room in allrows(conn,"SELECT * FROM rooms WHERE game_id=? AND status='playing'",(GAME,)):
            match=load_match(conn,room)
            if match and engine.tick(match,now):save_match(conn,room,match)
        for person in allrows(conn,"SELECT m.* FROM members m JOIN rooms r ON r.id=m.room_id WHERE m.game_id=? AND r.status IN ('waiting','finished') AND m.last_seen<?",(GAME,now-120)):
            room=dict(conn.execute('SELECT * FROM rooms WHERE id=?',(person['room_id'],)).fetchone())
            remove_member(conn,room,person['user_id'],now)
        conn.execute('DELETE FROM mines_queue WHERE last_seen<?',(now-40,))
        conn.execute('DELETE FROM mines_people WHERE observer=1 AND last_seen<?',(now-120,))


async def sweeper(app):
    while True:
        await asyncio.sleep(1)
        sweep_once(app)
