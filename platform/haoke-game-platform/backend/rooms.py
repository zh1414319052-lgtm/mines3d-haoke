import asyncio
from collections import defaultdict
import json
import secrets
import time
import uuid
from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from .db import allrows, rowdict
from .models import GameEntry, ReadyUpdate, EmoteSend, MuteUpdate
from .security import digest, fail, user_required

router=APIRouter(tags=["房间与表情"])

class Hub:
    def __init__(self):
        self.sockets = {}  # websocket -> (user_id, session_hash)
        self.relay = None

    async def send(self, users, event):
        for ws,(uid,_) in list(self.sockets.items()):
            if uid in users:
                try:
                    await asyncio.wait_for(ws.send_json(event),timeout=2)
                except Exception:
                    self.sockets.pop(ws,None)

    async def revoke_session(self, session_hash):
        if self.relay:
            await self.relay.revoke(session_hash=session_hash)
        for ws,(_,sh) in list(self.sockets.items()):
            if sh==session_hash:
                self.sockets.pop(ws,None)
                try:
                    await ws.close(code=4001)
                except Exception:
                    pass

    async def revoke_user(self, user_id):
        if self.relay:
            await self.relay.revoke(uid=user_id)
        for ws,(uid,_) in list(self.sockets.items()):
            if uid==user_id:
                self.sockets.pop(ws,None)
                try:
                    await ws.close(code=4001)
                except Exception:
                    pass

    def online(self, user_id):
        return any(uid==user_id for uid,_ in self.sockets.values())

def get_game(conn,game_id,visible=True):
    game=rowdict(conn.execute("SELECT * FROM games WHERE id=?",(game_id,)).fetchone())
    if not game or (visible and game["status"]!="visible"):
        fail(404,"GAME_NOT_FOUND","游戏不存在或暂未开放")
    return game

def enter_game(conn,user,game_id):
    now=time.time()
    conn.execute("""INSERT INTO profiles VALUES(?,?,?,'{}',?,?)
        ON CONFLICT(user_id,game_id) DO UPDATE SET last_entered=excluded.last_entered""",
        (user["id"],game_id,user["nickname"],now,now))
    # At most one enter event per user/game per minute.
    if not conn.execute("SELECT 1 FROM events WHERE user_id=? AND game_id=? AND kind='game_enter' AND created_at>? LIMIT 1",
                        (user["id"],game_id,now-60)).fetchone():
        conn.execute("INSERT INTO events(user_id,game_id,kind,created_at) VALUES(?,?,'game_enter',?)",(user["id"],game_id,now))

def get_room(conn,code,require_open=False):
    room=rowdict(conn.execute("SELECT * FROM rooms WHERE code=?",(code.upper(),)).fetchone())
    if not room:
        fail(404,"ROOM_NOT_FOUND","房间不存在，请检查房间码")
    if require_open and (room["status"]!="waiting" or room["expires_at"]<time.time()):
        fail(410,"ROOM_CLOSED","房间已关闭或邀请已失效")
    return room

@router.get("/api/invitations/{code}",tags=["公开"])
def invitation(code:str,request:Request,game_id:str|None=None):
    """Read-only landing data: viewing a link never occupies a player seat."""
    with request.app.state.db.connect() as conn:
        room=get_room(conn,code,require_open=False)
        valid_status=('waiting','playing','finished') if room['game_id']=='mines3d' else ('waiting',)
        if room['status'] not in valid_status or room['expires_at']<time.time():
            fail(410,'ROOM_CLOSED','房间已关闭或邀请已失效')
        if game_id and game_id!=room["game_id"]:
            fail(409,"GAME_MISMATCH","邀请中的游戏与房间不一致")
        game=get_game(conn,room["game_id"])
        count=conn.execute("SELECT count(*) FROM members WHERE room_id=?",(room["id"],)).fetchone()[0]
        extra={}
        if game['id']=='mines3d':
            config=conn.execute('SELECT settings FROM mines_rooms WHERE room_id=?',(room['id'],)).fetchone()
            extra={'status':room['status'],'settings':json.loads(config['settings']),
                   'spectators':conn.execute('SELECT count(*) FROM mines_people WHERE room_id=? AND observer=1',(room['id'],)).fetchone()[0]}
        return {**extra,"code":room["code"],"game_id":game["id"],"game_title":game["title"],
                "member_count":count,"max_players":game["max_players"],"full":count>=game["max_players"],
                "expires_at":room["expires_at"],"client_integration":"server-authoritative" if game['id']=='mines3d' else game['integration'],"join_location":"game"}

def member_required(conn,room,user_id):
    member=conn.execute("SELECT * FROM members WHERE room_id=? AND user_id=?",(room["id"],user_id)).fetchone()
    if not member:
        fail(403,"NOT_A_MEMBER","请先加入这个房间")
    return member

def room_view(conn,room,hub=None):
    game=get_game(conn,room["game_id"],visible=False)
    members=allrows(conn,"""SELECT m.user_id,m.ready,m.joined_at,m.last_seen,u.nickname,u.avatar
        FROM members m JOIN users u ON u.id=m.user_id WHERE room_id=? ORDER BY joined_at,user_id""",(room["id"],))
    for m in members:
        m["online"]=(hub.online(m["user_id"]) if hub else False) or time.time()-m["last_seen"]<35
        m["ready"]=bool(m["ready"])
    return {**room,"game_title":game["title"],"max_players":game["max_players"],"min_players":game["min_players"],
            "members":members,"battle_integration":"host-relay" if room["game_id"]=="liquid-wars" else "server-authoritative" if room['game_id']=='mines3d' else "pending",
            "human_count":len(members),"computer_count":max(0,6-len(members)) if room["game_id"]=="liquid-wars" else 0,
            "mode": (conn.execute("SELECT mode FROM online_room_settings WHERE room_id=?",(room["id"],)).fetchone() or [0])[0]}

async def publish_room(app,room_id,extra_users=()):
    with app.state.db.connect() as conn:
        room=rowdict(conn.execute("SELECT * FROM rooms WHERE id=?",(room_id,)).fetchone())
        if not room:
            return
        view=room_view(conn,room,app.state.hub)
    recipients={m["user_id"] for m in view["members"]}|set(extra_users)
    await app.state.hub.send(recipients,{"type":"room","room":view})

def remove_member(conn,room,user_id):
    if room['game_id']=='mines3d':
        from . import mines
        mines.remove_member(conn,room,user_id,time.time())
        return
    if room["status"]=="playing" and room["host_id"]==user_id:
        conn.execute("DELETE FROM members WHERE room_id=?",(room["id"],))
        conn.execute("UPDATE rooms SET status='closed',updated_at=? WHERE id=?",(time.time(),room["id"]))
        return
    conn.execute("DELETE FROM members WHERE room_id=? AND user_id=?",(room["id"],user_id))
    remaining=conn.execute("SELECT user_id FROM members WHERE room_id=? ORDER BY joined_at,user_id",(room["id"],)).fetchall()
    if not remaining:
        conn.execute("UPDATE rooms SET status='closed',updated_at=? WHERE id=?",(time.time(),room["id"]))
    elif room["host_id"]==user_id:
        conn.execute("UPDATE rooms SET host_id=?,updated_at=? WHERE id=?",(remaining[0]["user_id"],time.time(),room["id"]))
    else:
        conn.execute("UPDATE rooms SET updated_at=? WHERE id=?",(time.time(),room["id"]))

@router.post("/api/games/{game_id}/enter")
def game_enter(game_id:str,request:Request,p=Depends(user_required)):
    with request.app.state.db.connect(write=True) as conn:
        get_game(conn,game_id)
        enter_game(conn,p.user,game_id)
    return {"ok":True}

@router.get("/api/rooms")
def rooms(request:Request,game_id:str="liquid-wars"):
    with request.app.state.db.connect() as conn:
        get_game(conn,game_id)
        result=allrows(conn,"""SELECT r.*,g.title AS game_title,g.max_players,
            (SELECT count(*) FROM members m WHERE m.room_id=r.id) AS member_count,
            u.nickname AS host_name FROM rooms r JOIN games g ON g.id=r.game_id JOIN users u ON u.id=r.host_id
            WHERE r.game_id=? AND r.status='waiting' AND r.expires_at>? ORDER BY r.created_at DESC LIMIT 100""",(game_id,time.time()))
    return {"rooms":result}

@router.post("/api/rooms")
async def create_room(body:GameEntry,request:Request,p=Depends(user_required)):
    if body.game_id=='mines3d':fail(409,'USE_MINES_API','请更新扫雷客户端 / Use the Mines3D room API')
    now=time.time()
    with request.app.state.db.connect(write=True) as conn:
        get_game(conn,body.game_id)
        conn.execute("DELETE FROM match_queue WHERE user_id=? AND game_id=?",(p.user["id"],body.game_id))
        existing=conn.execute("SELECT r.* FROM members m JOIN rooms r ON r.id=m.room_id WHERE m.game_id=? AND m.user_id=? AND r.status IN ('waiting','playing')",(body.game_id,p.user["id"])).fetchone()
        if existing:
            return {"room":room_view(conn,dict(existing),request.app.state.hub),"existing":True}
        rid=str(uuid.uuid4())
        for _ in range(10):
            code="".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
            if not conn.execute("SELECT 1 FROM rooms WHERE code=?",(code,)).fetchone():
                break
        else:
            fail(503,"CODE_ALLOCATION_FAILED","房间码暂不可用，请重试")
        conn.execute("INSERT INTO rooms VALUES(?,?,?,?,'waiting',?,?,?)",(rid,code,body.game_id,p.user["id"],now,now,now+86400))
        conn.execute("INSERT INTO members VALUES(?,?,?,0,?,?)",(rid,p.user["id"],body.game_id,now,now))
        enter_game(conn,p.user,body.game_id)
        view=room_view(conn,get_room(conn,code),request.app.state.hub)
    await publish_room(request.app,rid)
    return {"room":view,"existing":False}

@router.get("/api/rooms/{code}")
def room_detail(code:str,request:Request,p=Depends(user_required)):
    with request.app.state.db.connect() as conn:
        room=get_room(conn,code)
        view=room_view(conn,room,request.app.state.hub)
        is_member=any(m["user_id"]==p.user["id"] for m in view["members"])
        messages=allrows(conn,"""SELECT * FROM (SELECT m.*,u.nickname,u.avatar FROM messages m JOIN users u ON u.id=m.user_id
            WHERE m.room_id=? AND m.created_at>? AND m.user_id NOT IN (SELECT target_id FROM mutes WHERE user_id=?)
            ORDER BY m.id DESC LIMIT 30) ORDER BY id""",(room["id"],time.time()-300,p.user["id"])) if is_member else []
    return {"room":view,"is_member":is_member,"messages":messages}

@router.post("/api/rooms/{code}/join")
async def join_room(code:str,body:GameEntry,request:Request,p=Depends(user_required)):
    if body.game_id=='mines3d':fail(409,'USE_MINES_API','请使用扫雷游戏内加入 / Use the Mines3D room API')
    with request.app.state.db.connect(write=True) as conn:
        room=get_room(conn,code,require_open=True)
        if room["game_id"]!=body.game_id:
            fail(409,"GAME_MISMATCH","这个邀请属于另一款游戏")
        game=get_game(conn,body.game_id)
        conn.execute("DELETE FROM match_queue WHERE user_id=? AND game_id=?",(p.user["id"],body.game_id))
        if conn.execute("SELECT 1 FROM members WHERE room_id=? AND user_id=?",(room["id"],p.user["id"])).fetchone():
            conn.execute("UPDATE members SET last_seen=? WHERE room_id=? AND user_id=?",(time.time(),room["id"],p.user["id"]))
        else:
            existing=conn.execute("SELECT r.code FROM members m JOIN rooms r ON m.room_id=r.id WHERE m.game_id=? AND m.user_id=?",(body.game_id,p.user["id"])).fetchone()
            if existing:
                fail(409,"ALREADY_IN_ROOM","你已在房间 "+existing["code"]+"，请先退出")
            if conn.execute("SELECT count(*) FROM members WHERE room_id=?",(room["id"],)).fetchone()[0]>=game["max_players"]:
                fail(409,"ROOM_FULL","房间已满，最多允许6名玩家")
            conn.execute("INSERT INTO members VALUES(?,?,?,0,?,?)",(room["id"],p.user["id"],body.game_id,time.time(),time.time()))
        enter_game(conn,p.user,body.game_id)
        view=room_view(conn,room,request.app.state.hub)
    await publish_room(request.app,room["id"])
    return {"room":view}

@router.post("/api/rooms/{code}/leave")
async def leave_room(code:str,request:Request,p=Depends(user_required)):
    with request.app.state.db.connect(write=True) as conn:
        room=get_room(conn,code)
        remove_member(conn,room,p.user["id"])
    if room['game_id']=='mines3d':
        await publish_room(request.app,room['id'],[p.user['id']])
        return {'ok':True}
    if room["status"]=="playing" and room["host_id"]==p.user["id"]:
        await request.app.state.relay.close_room(room["id"])
    elif room["status"]=="playing":
        await request.app.state.relay.revoke(uid=p.user["id"])
    await publish_room(request.app,room["id"],[p.user["id"]])
    return {"ok":True}

@router.post("/api/rooms/{code}/ready")
async def set_ready(code:str,body:ReadyUpdate,request:Request,p=Depends(user_required)):
    with request.app.state.db.connect(write=True) as conn:
        room=get_room(conn,code,require_open=True)
        if room['game_id']=='mines3d':fail(409,'USE_MINES_API','请确认扫雷房间规则后准备 / Use the Mines3D ready API')
        member_required(conn,room,p.user["id"])
        conn.execute("UPDATE members SET ready=?,last_seen=? WHERE room_id=? AND user_id=?",(int(body.ready),time.time(),room["id"],p.user["id"]))
    await publish_room(request.app,room["id"])
    return {"ok":True}

@router.post("/api/rooms/{code}/heartbeat")
def heartbeat(code:str,request:Request,p=Depends(user_required)):
    with request.app.state.db.connect(write=True) as conn:
        room=get_room(conn,code)
        if room["status"] not in ("waiting","playing"):
            fail(410,"ROOM_CLOSED","房间已关闭")
        member_required(conn,room,p.user["id"])
        conn.execute("UPDATE members SET last_seen=? WHERE room_id=? AND user_id=?",(time.time(),room["id"],p.user["id"]))
    return {"ok":True}

@router.post("/api/rooms/{code}/start")
async def start_room(code:str,request:Request,p=Depends(user_required)):
    from .online import native_members
    with request.app.state.db.connect(write=True) as conn:
        room=get_room(conn,code,require_open=True)
        if room['game_id']=='mines3d':fail(409,'USE_MINES_API','请在扫雷中开始 / Use the Mines3D start API')
        if room["host_id"]!=p.user["id"]:
            fail(403,"HOST_REQUIRED","只有房主可以发起对局")
        game=get_game(conn,room["game_id"])
        members=allrows(conn,"SELECT * FROM members WHERE room_id=?",(room["id"],))
        if len(members)<game["min_players"]:
            fail(409,"NOT_ENOUGH_PLAYERS",f"至少需要{game['min_players']}名玩家")
        if any(not m["ready"] or time.time()-m["last_seen"]>35 for m in members):
            fail(409,"NOT_READY","请等待所有玩家在线并准备")
        native_members(conn,room)
        conn.execute("UPDATE rooms SET status='playing',updated_at=? WHERE id=?",(time.time(),room["id"]))
    await publish_room(request.app,room["id"])
    return {"ok":True,"state":"playing"}

@router.post("/api/rooms/{code}/emotes")
async def send_emote(code:str,body:EmoteSend,request:Request,p=Depends(user_required)):
    now=time.time()
    with request.app.state.db.connect(write=True) as conn:
        room=get_room(conn,code)
        if room["status"] not in ("waiting","playing"):
            fail(410,"ROOM_CLOSED","房间已关闭")
        member_required(conn,room,p.user["id"])
        if not conn.execute("SELECT 1 FROM emotes WHERE id=? AND enabled=1",(body.emote_id,)).fetchone():
            fail(400,"EMOTE_NOT_ALLOWED","只能发送已启用的官方表情")
        latest=conn.execute("SELECT created_at FROM messages WHERE user_id=? ORDER BY id DESC LIMIT 1",(p.user["id"],)).fetchone()
        if latest and now-latest[0]<request.app.state.config.emote_cooldown:
            fail(429,"EMOTE_COOLDOWN","表情发送间隔为3秒，请稍等")
        cursor=conn.execute("INSERT INTO messages(room_id,user_id,emote_id,created_at) VALUES(?,?,?,?)",(room["id"],p.user["id"],body.emote_id,now))
        event={"id":cursor.lastrowid,"room_id":room["id"],"user_id":p.user["id"],"emote_id":body.emote_id,"created_at":now,"nickname":p.user["nickname"],"avatar":p.user["avatar"]}
        recipients={r[0] for r in conn.execute("""SELECT user_id FROM members WHERE room_id=?
            AND user_id NOT IN (SELECT user_id FROM mutes WHERE target_id=?)""",(room["id"],p.user["id"]))}
    await request.app.state.hub.send(recipients,{"type":"emote","message":event})
    return {"message":event}

@router.put("/api/me/mutes/{target_id}")
def mute(target_id:str,body:MuteUpdate,request:Request,p=Depends(user_required)):
    with request.app.state.db.connect(write=True) as conn:
        if target_id==p.user["id"] or not conn.execute("SELECT 1 FROM users WHERE id=?",(target_id,)).fetchone():
            fail(400,"INVALID_TARGET","请选择其他玩家")
        if body.muted:
            conn.execute("INSERT OR IGNORE INTO mutes VALUES(?,?)",(p.user["id"],target_id))
        else:
            conn.execute("DELETE FROM mutes WHERE user_id=? AND target_id=?",(p.user["id"],target_id))
    return {"ok":True,"muted":body.muted}

@router.post("/api/realtime-ticket")
def realtime_ticket(request:Request,p=Depends(user_required)):
    ticket=secrets.token_urlsafe(32)
    with request.app.state.db.connect(write=True) as conn:
        conn.execute("INSERT INTO ws_tickets VALUES(?,?,?,?)",(digest(ticket),p.session_hash,p.user["id"],time.time()+30))
    return {"ticket":ticket,"expires_in":30}

@router.websocket("/ws")
async def websocket(ws:WebSocket):
    app=ws.app
    origin=ws.headers.get("origin")
    if origin and origin not in app.state.config.allowed_origins:
        await ws.close(code=1008)
        return
    # Short-lived one-use ticket; actual session tokens never appear in URLs.
    ticket=ws.query_params.get("ticket","")
    with app.state.db.connect(write=True) as conn:
        row=conn.execute("""SELECT w.* FROM ws_tickets w JOIN sessions s ON s.token_hash=w.session_hash
            JOIN users u ON u.id=w.user_id WHERE w.hash=? AND w.expires_at>? AND s.expires_at>? AND u.status='active'""",(digest(ticket),time.time(),time.time())).fetchone()
        if row:
            conn.execute("DELETE FROM ws_tickets WHERE hash=?",(digest(ticket),))
            uid,session_hash=row["user_id"],row["session_hash"]
    if not row:
        await ws.close(code=1008)
        return
    await ws.accept()
    app.state.hub.sockets[ws]=(uid,session_hash)
    try:
        with app.state.db.connect(write=True) as conn:
            conn.execute("UPDATE members SET last_seen=? WHERE user_id=?",(time.time(),uid))
            ids=[r[0] for r in conn.execute("SELECT room_id FROM members WHERE user_id=?",(uid,))]
        await ws.send_json({"type":"connected","user_id":uid})
        for rid in ids:
            await publish_room(app,rid)
        while True:
            raw=await asyncio.wait_for(ws.receive_text(),timeout=45)
            if len(raw)>256:
                await ws.close(code=1009)
                break
            try:
                data=json.loads(raw)
            except ValueError:
                await ws.send_json({"type":"error","code":"INVALID_MESSAGE"})
                continue
            if data!={"type":"ping"}:
                await ws.send_json({"type":"error","code":"ONLY_HEARTBEAT_ALLOWED"})
                continue
            with app.state.db.connect(write=True) as conn:
                valid=conn.execute("SELECT 1 FROM sessions s JOIN users u ON u.id=s.user_id WHERE token_hash=? AND expires_at>? AND u.status='active'",(session_hash,time.time())).fetchone()
                if valid:
                    conn.execute("UPDATE members SET last_seen=? WHERE user_id=?",(time.time(),uid))
            if not valid:
                await ws.close(code=4001)
                break
            await ws.send_json({"type":"pong"})
    except (WebSocketDisconnect,asyncio.TimeoutError,RuntimeError):
        pass
    finally:
        app.state.hub.sockets.pop(ws,None)
        with app.state.db.connect() as conn:
            ids=[r[0] for r in conn.execute("SELECT room_id FROM members WHERE user_id=?",(uid,))]
        for rid in ids:
            await publish_room(app,rid)

async def sweep_once(app):
    changed=defaultdict(set)
    now=time.time()
    with app.state.db.connect(write=True) as conn:
        stale=allrows(conn,"SELECT * FROM members WHERE last_seen<? AND game_id!='mines3d'",(now-app.state.config.reconnect_grace,))
        for member in stale:
            room=rowdict(conn.execute("SELECT * FROM rooms WHERE id=?",(member["room_id"],)).fetchone())
            remove_member(conn,room,member["user_id"])
            changed[room["id"]].add(member["user_id"])
        expired=allrows(conn,"SELECT * FROM rooms WHERE status='waiting' AND expires_at<?",(now,))
        for room in expired:
            changed[room["id"]].update(r[0] for r in conn.execute("SELECT user_id FROM members WHERE room_id=?",(room["id"],)))
            conn.execute("DELETE FROM members WHERE room_id=?",(room["id"],))
            conn.execute("UPDATE rooms SET status='closed' WHERE id=?",(room["id"],))
        conn.execute("DELETE FROM ws_tickets WHERE expires_at<?",(now,))
        conn.execute("DELETE FROM sessions WHERE expires_at<?",(now,))
        conn.execute("DELETE FROM challenges WHERE created_at<?",(now-86400,))
        conn.execute("DELETE FROM messages WHERE created_at<?",(now-86400,))
        conn.execute("DELETE FROM idempotency WHERE created_at<?",(now-7*86400,))
        conn.execute("DELETE FROM api_requests WHERE created_at<?",(now-90*86400,))
    for rid,users in changed.items():
        await publish_room(app,rid,users)
    from .online import sweep_online
    await sweep_online(app)

async def sweeper(app):
    while True:
        await asyncio.sleep(10)
        await sweep_once(app)
