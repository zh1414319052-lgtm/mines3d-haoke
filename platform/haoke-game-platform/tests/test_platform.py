from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time
import uuid
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.config import Settings
from backend.security import digest
from backend.rooms import sweep_once
import asyncio

@pytest.fixture
def app(tmp_path):
    cfg=Settings(data_dir=tmp_path,secret="test-only-secret-32-chars-or-more",otp_cooldown=0,emote_cooldown=3)
    return create_app(cfg)

def client(app):
    return TestClient(app,client=("127.0.0.1",50000))

def signin(app,email,mode="web",purpose="signin"):
    c=client(app)
    d=c.post("/api/auth/code",json={"email":email,"purpose":purpose}).json()
    assert "challenge_id" in d,d
    code=c.get("/api/dev/mailbox",params={"challenge_id":d["challenge_id"]}).json()["code"]
    r=c.post("/api/auth/verify",json={"challenge_id":d["challenge_id"],"code":code,"client":mode})
    assert r.status_code==200,r.text
    if mode=="web":
        c.headers["X-CSRF-Token"]=r.json()["csrf"]
    else:
        c.headers["Authorization"]="Bearer "+r.json()["access_token"]
    return c,r.json()["user"]

def write(c,method,path,body=None,key=None):
    return c.request(method,path,json=body or {},headers={"Idempotency-Key":key or str(uuid.uuid4())})

def game_data(gid):
    return {"id":gid,"title":"隔离验证游戏","tagline":"不同玩法共用平台账号","description":"仅在自动测试数据库中使用","genre":"益智","status":"visible","min_players":2,"max_players":6}

def test_auth_canonical_registration_and_errors(app):
    c=client(app)
    d=c.post("/api/auth/code",json={"email":"Player@Example.com"}).json()
    code=c.get("/api/dev/mailbox",params={"challenge_id":d["challenge_id"]}).json()["code"]
    assert c.post("/api/auth/verify",json={"challenge_id":d["challenge_id"],"code":"xxxxxx"}).status_code==422
    good=c.post("/api/auth/verify",json={"challenge_id":d["challenge_id"],"code":code})
    assert good.status_code==200
    assert good.json()["is_new"] is True
    assert good.json()["user"]["email"]=="player@example.com"
    uid=good.json()["user"]["id"]
    assert c.post("/api/auth/verify",json={"challenge_id":d["challenge_id"],"code":code}).status_code==400
    again,u=signin(app,"PLAYER@example.com")
    assert u["id"]==uid
    with app.state.db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM users").fetchone()[0]==1
    assert again.get("/api/admin/users").status_code==403
    assert c.patch("/api/me",json={"nickname":"不应该成功","avatar":0}).status_code==403
    assert again.patch("/api/me",json={"nickname":"小液滴","avatar":1}).status_code==200
    assert again.post("/api/auth/logout").status_code==200
    assert again.get("/api/me").json()["user"] is None
    assert c.post("/api/auth/code",json={"email":"no-mail"}).status_code==422

def test_wrong_expired_codes_and_delivery_scope(app):
    c=client(app)
    d=c.post("/api/auth/code",json={"email":"attempt@example.com"}).json()
    real=c.get("/api/dev/mailbox",params={"challenge_id":d["challenge_id"]}).json()["code"]
    wrong="000000" if real!="000000" else "111111"
    for _ in range(5):
        assert c.post("/api/auth/verify",json={"challenge_id":d["challenge_id"],"code":wrong}).status_code==400
    assert c.post("/api/auth/verify",json={"challenge_id":d["challenge_id"],"code":real}).status_code==400
    d=c.post("/api/auth/code",json={"email":"expire@example.com"}).json()
    with app.state.db.connect(write=True) as conn:
        conn.execute("UPDATE challenges SET expires_at=0 WHERE id=?",(d["challenge_id"],))
    assert c.post("/api/auth/verify",json={"challenge_id":d["challenge_id"],"code":"123456"}).status_code==400
    remote=TestClient(app,client=("192.168.1.10",50000))
    assert remote.get("/api/dev/mailbox?challenge_id="+d["challenge_id"],headers={"X-Forwarded-For":"127.0.0.1"}).status_code==404
    assert not remote.get("/api/config").json()["dev_mailbox_available"]
    assert c.post("/api/auth/code",headers={"Origin":"https://untrusted.example"},json={"email":"other@example.com"}).status_code==403
    app.state.config.otp_cooldown=60
    c.post("/api/auth/code",json={"email":"cooldown@example.com"})
    assert c.post("/api/auth/code",json={"email":"cooldown@example.com"}).status_code==429

def test_recovery_revokes_previous_web_and_native_sessions(app):
    first,user=signin(app,"recover@example.com")
    native,_=signin(app,"recover@example.com","native")
    assert native.get("/api/me").json()["user"]["id"]==user["id"]
    recovered,_=signin(app,"recover@example.com",purpose="recovery")
    assert first.get("/api/me").json()["user"] is None
    assert native.get("/api/me").json()["user"] is None
    assert recovered.get("/api/me").json()["user"]["id"]==user["id"]

def test_six_player_capacity_and_atomic_race(app):
    players=[signin(app,f"player{i}@example.com")[0] for i in range(8)]
    created=players[0].post("/api/rooms",json={"game_id":"liquid-wars"}).json()["room"]
    code=created["code"]
    for c in players[1:5]:
        assert c.post(f"/api/rooms/{code}/join",json={"game_id":"liquid-wars"}).status_code==200
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(lambda c:c.post(f"/api/rooms/{code}/join",json={"game_id":"liquid-wars"}).status_code,players[5:]))
    assert results.count(200)==1
    assert results.count(409)==2
    detail=players[0].get("/api/rooms/"+code).json()
    assert len(detail["room"]["members"])==6
    assert players[0].post(f"/api/rooms/{code}/join",json={"game_id":"liquid-wars"}).status_code==200
    duplicate=players[0].post("/api/rooms",json={"game_id":"liquid-wars"}).json()
    assert duplicate["existing"] is True and duplicate["room"]["code"]==code
    assert len(players[0].get("/api/rooms/"+code).json()["room"]["members"])==6
    assert players[0].post(f"/api/rooms/{code}/leave").status_code==200
    now=players[1].get("/api/rooms/"+code).json()["room"]
    assert now["host_id"]!=created["host_id"] and len(now["members"])==5

def test_cross_game_profiles_and_invite_mismatch(app):
    admin,_=signin(app,"owner@haoke.local")
    assert write(admin,"POST","/api/admin/games",game_data("puzzle")).status_code==200
    player,user=signin(app,"isolation@example.com")
    for gid in ("puzzle","liquid-wars"):
        assert player.post("/api/games/"+gid+"/enter").status_code==200
    with app.state.db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM profiles WHERE user_id=?",(user["id"],)).fetchone()[0]==2
    body={"nickname":"只修改益智游戏","data":{"level":7}}
    assert write(admin,"PUT",f"/api/admin/games/puzzle/profiles/{user['id']}",body).status_code==200
    with app.state.db.connect() as conn:
        assert conn.execute("SELECT data FROM profiles WHERE user_id=? AND game_id='liquid-wars'",(user["id"],)).fetchone()[0]=="{}"
    room=player.post("/api/rooms",json={"game_id":"puzzle"}).json()["room"]
    stranger,_=signin(app,"visitor@example.com")
    assert stranger.post("/api/rooms/"+room["code"]+"/join",json={"game_id":"liquid-wars"}).status_code==409
    assert all(r["game_id"]!="puzzle" for r in stranger.get("/api/rooms").json()["rooms"])

def test_emote_allowlist_cooldown_mute_and_websocket(app):
    c1,u1=signin(app,"host@example.com")
    c2,u2=signin(app,"guest@example.com")
    room=c1.post("/api/rooms",json={"game_id":"liquid-wars"}).json()["room"]
    code=room["code"]
    c2.post(f"/api/rooms/{code}/join",json={"game_id":"liquid-wars"})
    assert c1.post(f"/api/rooms/{code}/emotes",json={"text":"不允许的聊天内容"}).status_code==422
    assert c1.post(f"/api/rooms/{code}/emotes",json={"emote_id":"hello","text":"也不允许"}).status_code==422
    assert c1.post(f"/api/rooms/{code}/emotes",json={"emote_id":"https://example.com/image.png"}).status_code==400
    t1=c1.post("/api/realtime-ticket").json()["ticket"]
    t2=c2.post("/api/realtime-ticket").json()["ticket"]
    with c1.websocket_connect("/ws?ticket="+t1) as ws1:
        assert ws1.receive_json()["type"]=="connected"
        ws1.receive_json()
        with c2.websocket_connect("/ws?ticket="+t2) as ws2:
            assert ws2.receive_json()["type"]=="connected"
            ws2.receive_json()
            ws1.receive_json()
            assert c1.post(f"/api/rooms/{code}/emotes",json={"emote_id":"hello"}).status_code==200
            assert ws1.receive_json()["message"]["emote_id"]=="hello"
            assert ws2.receive_json()["message"]["emote_id"]=="hello"
            assert c1.post(f"/api/rooms/{code}/emotes",json={"emote_id":"thanks"}).status_code==429
            assert c2.put("/api/me/mutes/"+u1["id"],json={"muted":True}).status_code==200
            assert c2.get("/api/rooms/"+code).json()["messages"]==[]
            ws2.send_json({"text":"不能经websocket聊天"})
            assert ws2.receive_json()["code"]=="ONLY_HEARTBEAT_ALLOWED"
            ws2.send_json({"type":"ping"})
            assert ws2.receive_json()["type"]=="pong"
    # A consumed ticket cannot be reused.
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with c1.websocket_connect("/ws?ticket="+t1):
            pass

def test_ready_start_reconnect_expiry(app):
    c1,u1=signin(app,"host@example.com");c2,u2=signin(app,"guest@example.com")
    r=c1.post("/api/rooms",json={"game_id":"liquid-wars"}).json()["room"];code=r["code"]
    assert c1.post("/api/rooms/"+code+"/start").json()["error"]["code"]=="NOT_READY"
    c2.post("/api/rooms/"+code+"/join",json={"game_id":"liquid-wars"})
    assert c2.post("/api/rooms/"+code+"/start").status_code==403
    for c in (c1,c2):
        assert c.post("/api/rooms/"+code+"/ready",json={"ready":True}).status_code==200
    assert c1.post("/api/rooms/"+code+"/start").json()["error"]["code"]=="GAME_CLIENT_PENDING"
    with app.state.db.connect(write=True) as conn:
        conn.execute("UPDATE members SET last_seen=? WHERE user_id=?",(time.time()-91,u1["id"]))
    asyncio.run(sweep_once(app))
    current=c2.get("/api/rooms/"+code).json()["room"]
    assert current["host_id"]==u2["id"] and len(current["members"])==1
    c2.post("/api/rooms/"+code+"/leave")
    assert c1.post("/api/rooms/"+code+"/join",json={"game_id":"liquid-wars"}).status_code==410

def test_admin_keys_write_read_rotation_revocation_audit_idempotency(app):
    owner,_=signin(app,"owner@haoke.local"); outsider,_=signin(app,"outsider@example.com")
    assert outsider.get("/api/admin/settings").status_code==403
    assert client(app).get("/api/admin/stats").status_code==401
    keybody={"name":"测试AI","scope":"admin:full","expires_days":1}
    created=write(owner,"POST","/api/admin/keys",keybody,key="creation-idem-key")
    assert created.status_code==200,created.text
    token=created.json()["token"];kid=created.json()["key"]["id"]
    assert write(owner,"POST","/api/admin/keys",keybody,key="creation-idem-key").json()["token"] is None
    ai=client(app);ai.headers["Authorization"]="Bearer "+token
    current=ai.get("/api/admin/settings").json()["settings"]
    updated={**current,"announcement":"来自授权AI的真实本地修改"}
    first=write(ai,"PUT","/api/admin/settings",updated,key="settings-update-idem")
    assert first.status_code==200,first.text
    replay=write(ai,"PUT","/api/admin/settings",updated,key="settings-update-idem")
    assert replay.json()==first.json()
    assert write(ai,"PUT","/api/admin/settings",{**updated,"announcement":"不同内容"},key="settings-update-idem").status_code==409
    assert client(app).get("/api/config").json()["site"]["announcement"]==updated["announcement"]
    audit=owner.get("/api/admin/audit").json()["entries"]
    assert sum(x["action"]=="settings.update" for x in audit)==1
    assert any(x["actor"]=="key:"+kid for x in audit)
    assert token not in str(audit)
    ro=write(owner,"POST","/api/admin/keys",{"name":"只读","scope":"admin:read","expires_days":1}).json()
    readonly=client(app);readonly.headers["Authorization"]="Bearer "+ro["token"]
    assert readonly.get("/api/admin/stats").status_code==200
    assert write(readonly,"PUT","/api/admin/settings",updated).status_code==403
    rotated=write(owner,"POST","/api/admin/keys/"+kid+"/rotate").json()
    assert ai.get("/api/admin/settings").status_code==401
    ai.headers["Authorization"]="Bearer "+rotated["token"]
    assert ai.get("/api/admin/settings").status_code==200
    assert write(owner,"POST","/api/admin/keys/"+kid+"/revoke").status_code==200
    assert ai.get("/api/admin/settings").status_code==401
    with app.state.db.connect() as conn:
        assert token not in str([dict(x) for x in conn.execute("SELECT * FROM api_keys")])

def test_stats_real_counts_and_persistence(app):
    owner,_=signin(app,"owner@haoke.local")
    a,_=signin(app,"a@example.com");signin(app,"a@example.com");b,_=signin(app,"b@example.com")
    a.post("/api/games/liquid-wars/enter");a.post("/api/games/liquid-wars/enter")
    stats=owner.get("/api/admin/stats").json()
    assert stats["total_users"]==3 and stats["today_new"]==3
    assert stats["active_users"]==3 and stats["games"][0]["first_entries"]==1
    assert stats["games"][0]["active_users"]==1 and stats["games"][0]["matches"] == 0
    assert sum(x["registrations"] for x in stats["trend"])==3
    assert owner.get("/api/admin/stats?start=bad").status_code==400
    restored=create_app(app.state.config)
    assert restored.state.db.path==app.state.db.path
    check=client(restored);check.cookies.update(owner.cookies)
    assert check.get("/api/admin/stats").json()["total_users"]==3
    assert check.get("/api/me").json()["user"]["email"]=="owner@haoke.local"

def test_admin_disable_room_emote_and_boundaries(app):
    owner,_=signin(app,"owner@haoke.local");player,u=signin(app,"member@example.com")
    r=player.post("/api/rooms",json={"game_id":"liquid-wars"}).json()["room"]
    assert write(owner,"PUT","/api/admin/emotes/hello",{"label":"你好","enabled":False}).status_code==200
    assert player.post("/api/rooms/"+r["code"]+"/emotes",json={"emote_id":"hello"}).status_code==400
    assert write(owner,"POST","/api/admin/rooms/"+r["code"]+"/close").status_code==200
    assert not player.get("/api/me").json()["rooms"]
    assert write(owner,"PATCH","/api/admin/users/"+u["id"],{"nickname":u["nickname"],"role":"user","status":"suspended"}).status_code==200
    assert player.get("/api/me").json()["user"] is None
    assert write(owner,"POST","/api/admin/games/liquid-wars/releases",{"platform":"ios","version":"1","url":"javascript:alert(1)"}).status_code==422
    assert client(app).get("/api/not-a-real-route").status_code==404
    assert client(app).get("/api/config",headers={"Host":"evil.example"}).status_code==400

def test_production_requires_explicit_safe_configuration(tmp_path):
    with pytest.raises(RuntimeError):
        create_app(Settings(data_dir=tmp_path,env="production"))
