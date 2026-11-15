"""Native-client admission, atomic matchmaking and authenticated game-byte relay.

The existing Android host simulates the battle; this service never fabricates a result.
One worker is intentional: live relays are process-owned and restart ends old battles.
"""
import asyncio
from contextlib import suppress
import json
import secrets
import time
import uuid
from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from pydantic import Field
from .db import allrows, rowdict
from .models import StrictModel
from .security import digest, fail, user_required
from .rooms import get_game, get_room, member_required, enter_game, room_view, publish_room

router = APIRouter(tags=["游戏内联网"])
GAME = "liquid-wars"
PROTOCOL = 30
BUILD = 53

SCHEMA = """
CREATE TABLE IF NOT EXISTS native_clients(user_id TEXT NOT NULL,game_id TEXT NOT NULL,session_hash TEXT NOT NULL,protocol INTEGER NOT NULL,build INTEGER NOT NULL,last_seen REAL NOT NULL,PRIMARY KEY(user_id,game_id));
CREATE TABLE IF NOT EXISTS match_queue(user_id TEXT NOT NULL,game_id TEXT NOT NULL,protocol INTEGER NOT NULL,mode INTEGER NOT NULL,session_hash TEXT NOT NULL,queued_at REAL NOT NULL,last_seen REAL NOT NULL,PRIMARY KEY(user_id,game_id));
CREATE TABLE IF NOT EXISTS relay_tickets(hash TEXT PRIMARY KEY,user_id TEXT NOT NULL,session_hash TEXT NOT NULL,room_id TEXT NOT NULL,expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS battle_sessions(id TEXT PRIMARY KEY,room_id TEXT NOT NULL,game_id TEXT NOT NULL,host_id TEXT NOT NULL,started_at REAL NOT NULL,ended_at REAL,reason TEXT);
CREATE INDEX IF NOT EXISTS battle_sessions_room ON battle_sessions(room_id,started_at);
CREATE TABLE IF NOT EXISTS online_room_settings(room_id TEXT PRIMARY KEY,mode INTEGER NOT NULL DEFAULT 0);
"""

class ClientHello(StrictModel):
    game_id: str = GAME
    protocol: int = Field(ge=1, le=100000)
    build: int = Field(ge=1, le=1000000)

class MatchRequest(ClientHello):
    mode: int = Field(default=0, ge=0, le=1)

class BattleEnd(StrictModel):
    battle_id: str = Field(min_length=32,max_length=40)

def supported(body):
    if body.game_id != GAME:
        fail(409, "GAME_ADAPTER_PENDING", "这款游戏尚未接入联网适配器")
    if body.protocol != PROTOCOL or body.build < BUILD:
        fail(409, "UPDATE_REQUIRED", "请更新到支持公网联网的游戏版本")

def native_required(request: Request, p=Depends(user_required)):
    if not request.headers.get("authorization", "").startswith("Bearer "):
        fail(403, "NATIVE_REQUIRED", "请从游戏内进入联网大厅")
    return p

def admit(conn, body, p):
    supported(body)
    get_game(conn, body.game_id)
    conn.execute("INSERT INTO native_clients VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,game_id) DO UPDATE SET session_hash=excluded.session_hash,protocol=excluded.protocol,build=excluded.build,last_seen=excluded.last_seen",
                 (p.user["id"], body.game_id, p.session_hash, body.protocol, body.build, time.time()))

@router.post("/api/online/enter")
def online_enter(body: ClientHello, request: Request, p=Depends(native_required)):
    with request.app.state.db.connect(write=True) as conn:
        admit(conn, body, p)
        enter_game(conn, p.user, body.game_id)
    return {"ok": True, "protocol": PROTOCOL, "max_players": 6, "relay": "host-authoritative"}

def current_room(conn, uid, game_id):
    return rowdict(conn.execute("SELECT r.* FROM rooms r JOIN members m ON m.room_id=r.id WHERE m.user_id=? AND m.game_id=? AND r.status IN ('waiting','playing')", (uid, game_id)).fetchone())

def clean_queue(conn):
    conn.execute("DELETE FROM match_queue WHERE last_seen<? OR session_hash NOT IN (SELECT s.token_hash FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.expires_at>? AND u.status='active')", (time.time()-40, time.time()))

def resolve_match(conn, game_id, protocol, mode):
    game = get_game(conn, game_id)
    queued = allrows(conn, "SELECT * FROM match_queue WHERE game_id=? AND protocol=? AND mode=? ORDER BY queued_at,user_id LIMIT ?", (game_id, protocol, mode, game["max_players"]))
    if len(queued) < game["min_players"] or (len(queued) < game["max_players"] and time.time()-queued[0]["queued_at"] < 8):
        return
    rid, now = str(uuid.uuid4()), time.time()
    for _ in range(20):
        code = ''.join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
        if not conn.execute("SELECT 1 FROM rooms WHERE code=?", (code,)).fetchone():
            break
    else:
        fail(503, "ROOM_BUSY", "房间服务忙，请稍后重试")
    conn.execute("INSERT INTO rooms VALUES(?,?,?,?,'playing',?,?,?)", (rid, code, game_id, queued[0]["user_id"], now, now, now+86400))
    conn.execute("INSERT INTO online_room_settings VALUES(?,?)", (rid, mode))
    for i, q in enumerate(queued):
        conn.execute("INSERT INTO members VALUES(?,?,?,1,?,?)", (rid, q["user_id"], game_id, now+i*.001, now))
        conn.execute("DELETE FROM match_queue WHERE user_id=? AND game_id=?", (q["user_id"], game_id))

@router.post("/api/matchmaking/enqueue")
def enqueue(body: MatchRequest, request: Request, p=Depends(native_required)):
    with request.app.state.db.connect(write=True) as conn:
        admit(conn, body, p)
        enter_game(conn, p.user, body.game_id)
        clean_queue(conn)
        room = current_room(conn, p.user["id"], body.game_id)
        if room:
            return {"state": "room", "room": room_view(conn, room, request.app.state.hub)}
        conn.execute("INSERT INTO match_queue VALUES(?,?,?,?,?,?,?) ON CONFLICT(user_id,game_id) DO UPDATE SET last_seen=excluded.last_seen", (p.user["id"], body.game_id, body.protocol, body.mode, p.session_hash, time.time(), time.time()))
        resolve_match(conn, body.game_id, body.protocol, body.mode)
        return queue_view(conn, p, request.app.state.hub)

def queue_view(conn, p, hub):
    room = current_room(conn, p.user["id"], GAME)
    if room:
        return {"state": "room", "room": room_view(conn, room, hub)}
    q = conn.execute("SELECT * FROM match_queue WHERE user_id=? AND game_id=?", (p.user["id"], GAME)).fetchone()
    return {"state": "queued" if q else "idle", "queued_at": q["queued_at"] if q else None}

@router.get("/api/matchmaking/status")
def queue_status(request: Request, p=Depends(native_required)):
    with request.app.state.db.connect(write=True) as conn:
        clean_queue(conn)
        conn.execute("UPDATE match_queue SET last_seen=? WHERE user_id=? AND session_hash=?", (time.time(), p.user["id"], p.session_hash))
        q = conn.execute("SELECT * FROM match_queue WHERE user_id=? AND game_id=?", (p.user["id"], GAME)).fetchone()
        if q:
            resolve_match(conn, q["game_id"], q["protocol"], q["mode"])
        return queue_view(conn, p, request.app.state.hub)

@router.post("/api/matchmaking/cancel")
def queue_cancel(request: Request, p=Depends(native_required)):
    with request.app.state.db.connect(write=True) as conn:
        conn.execute("DELETE FROM match_queue WHERE user_id=?", (p.user["id"],))
        return queue_view(conn, p, request.app.state.hub)

def native_members(conn, room):
    members = allrows(conn, "SELECT m.*,n.protocol,n.build,n.session_hash,s.expires_at,u.status AS user_status FROM members m LEFT JOIN native_clients n ON n.user_id=m.user_id AND n.game_id=m.game_id LEFT JOIN sessions s ON s.token_hash=n.session_hash LEFT JOIN users u ON u.id=m.user_id WHERE m.room_id=?", (room["id"],))
    if room["game_id"] != GAME or any(m["protocol"] != PROTOCOL or (m["build"] or 0) < BUILD or (m["expires_at"] or 0) < time.time() or m["user_status"] != "active" for m in members):
        fail(409, "GAME_CLIENT_PENDING", "请所有玩家使用最新游戏客户端进入房间")

@router.post("/api/online/rooms/{code}/ticket")
def relay_ticket(code: str, request: Request, p=Depends(native_required)):
    token = secrets.token_urlsafe(32)
    with request.app.state.db.connect(write=True) as conn:
        room = get_room(conn, code)
        member_required(conn, room, p.user["id"])
        if room["status"] != "playing":
            fail(409, "ROOM_NOT_STARTED", "请先等待全员准备并进入游戏设置")
        native_members(conn, room)
        conn.execute("INSERT INTO relay_tickets VALUES(?,?,?,?,?)", (digest(token), p.user["id"], p.session_hash, room["id"], time.time()+30))
    return {"ticket": token, "path": "/ws/game", "expires_in": 30}

@router.post("/api/online/rooms/{code}/battle-start")
def battle_start(code: str, request: Request, p=Depends(native_required)):
    with request.app.state.db.connect(write=True) as conn:
        room = get_room(conn, code)
        if room["host_id"] != p.user["id"] or room["status"] != "playing":
            fail(403, "HOST_REQUIRED", "只有当前房主可以开始战斗")
        peers = request.app.state.relay.rooms.get(room["id"], {})
        count = conn.execute("SELECT count(*) FROM members WHERE room_id=?", (room["id"],)).fetchone()[0]
        if count < get_game(conn,room["game_id"])["min_players"] or len(peers) != count:
            fail(409, "PEERS_CONNECTING", "请等待所有玩家完成连接")
        old = conn.execute("SELECT id FROM battle_sessions WHERE room_id=? AND ended_at IS NULL", (room["id"],)).fetchone()
        if old:
            return {"ok": True, "battle_id": old[0]}
        bid = str(uuid.uuid4())
        conn.execute("INSERT INTO battle_sessions VALUES(?,?,?,?,?,NULL,NULL)", (bid, room["id"], room["game_id"], p.user["id"], time.time()))
    return {"ok": True, "battle_id": bid}

@router.post("/api/online/rooms/{code}/battle-end")
def battle_end(code: str, body: BattleEnd, request: Request, p=Depends(native_required)):
    with request.app.state.db.connect(write=True) as conn:
        room = get_room(conn, code)
        if room["host_id"] != p.user["id"]:
            fail(403, "HOST_REQUIRED", "只有房主可以结束本场记录")
        conn.execute("UPDATE battle_sessions SET ended_at=?,reason='host_returned' WHERE room_id=? AND id=? AND ended_at IS NULL", (time.time(), room["id"],body.battle_id))
    return {"ok": True}

class RelayHub:
    def __init__(self, app):
        self.app = app
        self.rooms = {}  # room -> slot -> (ws, uid, session_hash)
        self.locks = {}  # serialize sends per socket
        self.ready = set()

    async def send(self, ws, data):
        lock = self.locks.get(ws)
        if lock is None:
            raise RuntimeError("Relay closed")
        async with lock:
            await asyncio.wait_for(ws.send_bytes(data) if isinstance(data, bytes) else ws.send_json(data), 3)

    async def revoke(self, uid=None, session_hash=None):
        victims = [ws for peers in self.rooms.values() for ws,u,s in peers.values() if u == uid or s == session_hash]
        for ws in victims:
            with suppress(Exception):
                await ws.close(code=4001)

    async def close_room(self, rid, reason="host_left"):
        peers = self.rooms.pop(rid, {})
        with self.app.state.db.connect(write=True) as conn:
            conn.execute("UPDATE battle_sessions SET ended_at=?,reason=? WHERE room_id=? AND ended_at IS NULL", (time.time(), reason, rid))
            conn.execute("UPDATE rooms SET status='closed',updated_at=? WHERE id=?", (time.time(), rid))
            conn.execute("DELETE FROM members WHERE room_id=?", (rid,))
        for ws, _, _ in peers.values():
            with suppress(Exception):
                await ws.close(code=4000, reason=reason)

@router.websocket("/ws/game")
async def game_socket(ws: WebSocket):
    app, now = ws.app, time.time()
    origin = ws.headers.get("origin")
    if origin and origin not in app.state.config.allowed_origins:
        await ws.close(code=1008); return
    with app.state.db.connect(write=True) as conn:
        row = conn.execute("SELECT t.* FROM relay_tickets t JOIN sessions s ON s.token_hash=t.session_hash JOIN users u ON u.id=t.user_id WHERE t.hash=? AND t.expires_at>? AND s.expires_at>? AND s.kind='native' AND u.status='active'", (digest(ws.query_params.get("ticket", "")), now, now)).fetchone()
        if row:
            conn.execute("DELETE FROM relay_tickets WHERE hash=?", (row["hash"],))
            room = rowdict(conn.execute("SELECT * FROM rooms WHERE id=?", (row["room_id"],)).fetchone())
            members = allrows(conn, "SELECT user_id FROM members WHERE room_id=? ORDER BY joined_at,user_id", (row["room_id"],))
    if not row or not room or room["status"] != "playing" or row["user_id"] not in [m["user_id"] for m in members]:
        await ws.close(code=1008); return
    rid, uid, sh = row["room_id"], row["user_id"], row["session_hash"]
    ordered = [room["host_id"]]+[m["user_id"] for m in members if m["user_id"] != room["host_id"]]
    slot = ordered.index(uid)
    relay = app.state.relay
    peers = relay.rooms.setdefault(rid, {})
    if slot in peers or slot > 5:
        await ws.close(code=1013); return
    # Reserve before accept yields, so concurrent upgrades cannot duplicate a seat.
    peers[slot] = (ws, uid, sh)
    relay.locks[ws] = asyncio.Lock()
    try:
        await ws.accept()
        if slot:
            deadline = time.monotonic()+15
            while 0 not in peers or peers[0][0] not in relay.ready:
                if time.monotonic()>deadline:
                    await ws.close(code=1013); return
                await asyncio.sleep(.1)
        await relay.send(ws, {"type": "connected", "slot": slot})
        relay.ready.add(ws)
        if slot:
            await relay.send(peers[0][0], {"type": "join", "slot": slot})
        window, volume, verified = time.monotonic(), 0, 0
        while True:
            packet = await asyncio.wait_for(ws.receive(), 35)
            if packet["type"] == "websocket.disconnect":
                break
            if time.monotonic()-verified > 2:
                verified = time.monotonic()
                with app.state.db.connect(write=True) as conn:
                    valid = conn.execute("SELECT 1 FROM sessions s JOIN users u ON u.id=s.user_id JOIN members m ON m.user_id=u.id JOIN rooms r ON r.id=m.room_id WHERE s.token_hash=? AND s.expires_at>? AND u.status='active' AND m.room_id=? AND r.status='playing'", (sh, time.time(), rid)).fetchone()
                    if valid:
                        conn.execute("UPDATE members SET last_seen=? WHERE room_id=? AND user_id=?", (time.time(), rid, uid))
                if not valid:
                    await ws.close(code=4001); break
            if packet.get("text") is not None:
                if len(packet["text"]) > 128:
                    await ws.close(code=1009); break
                message = json.loads(packet["text"])
                if message == {"type": "ping"}:
                    await relay.send(ws, {"type": "pong"}); continue
                if slot == 0 and isinstance(message, dict) and set(message) == {"type", "slot"} and message["type"] == "close" and type(message["slot"]) is int and 1 <= message["slot"] <= 5:
                    target = peers.get(message["slot"])
                    if target:
                        await target[0].close(code=4000)
                    continue
                await ws.close(code=1008); break
            data = packet.get("bytes", b"")
            if not data or len(data) > 16384:
                await ws.close(code=1009); break
            if time.monotonic()-window > 1:
                window, volume = time.monotonic(), 0
            volume += len(data)
            if volume > 262144:
                await ws.close(code=1008); break
            if slot == 0:
                destination = data[0]
                if not 1 <= destination <= 5:
                    await ws.close(code=1008); break
                target = peers.get(destination)
                if target:
                    await relay.send(target[0], data[1:])
            elif 0 in peers:
                await relay.send(peers[0][0], bytes([slot])+data)
            else:
                break
    except (WebSocketDisconnect, asyncio.TimeoutError, RuntimeError, ValueError):
        pass
    finally:
        relay.locks.pop(ws, None)
        relay.ready.discard(ws)
        if peers.get(slot, (None,))[0] is ws:
            peers.pop(slot, None)
        if slot == 0:
            await relay.close_room(rid)
        elif 0 in peers:
            with suppress(Exception):
                await relay.send(peers[0][0], {"type": "left", "slot": slot})
        with suppress(Exception):
            await ws.close()

async def sweep_online(app):
    with app.state.db.connect(write=True) as conn:
        clean_queue(conn)
        conn.execute("DELETE FROM relay_tickets WHERE expires_at<?", (time.time(),))
        closed = [rid for rid in app.state.relay.rooms if not conn.execute("SELECT 1 FROM rooms WHERE id=? AND status='playing'", (rid,)).fetchone()]
    for rid in closed:
        await app.state.relay.close_room(rid, "room_closed")
