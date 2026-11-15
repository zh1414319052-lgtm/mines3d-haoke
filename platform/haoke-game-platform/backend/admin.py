from datetime import datetime, timedelta, timezone
import json
import time
import uuid
from fastapi import APIRouter, Depends, Query, Request
from .db import allrows, rowdict, setting_values
from .models import GameWrite, ReleaseWrite, SettingsWrite, UserAdminWrite, KeyCreate, EmoteAdminWrite, GameProfileWrite
from .rooms import get_game, get_room, publish_room, remove_member
from .security import admin_required, digest, fail, mutation, new_key

router=APIRouter(prefix="/api/admin",tags=["管理 API"])
CN=timezone(timedelta(hours=8))

def serialize_key(row):
    return {k:v for k,v in dict(row).items() if k!="token_hash"}

@router.get("/stats")
def stats(request:Request,start:str|None=None,end:str|None=None,p=Depends(admin_required)):
    today=datetime.now(CN).date()
    try:
        start_date=datetime.strptime(start,"%Y-%m-%d").date() if start else today-timedelta(days=6)
        end_date=datetime.strptime(end,"%Y-%m-%d").date() if end else today
    except ValueError:
        fail(400,"INVALID_DATE","日期格式应为 YYYY-MM-DD")
    if start_date>end_date or (end_date-start_date).days>365 or end_date>today:
        fail(400,"INVALID_DATE_RANGE","选择不超过366天且不含未来日期的范围")
    lower=datetime.combine(start_date,datetime.min.time(),CN).timestamp()
    upper=datetime.combine(end_date+timedelta(days=1),datetime.min.time(),CN).timestamp()
    today_start=datetime.combine(today,datetime.min.time(),CN).timestamp()
    with request.app.state.db.connect() as conn:
        total=conn.execute("SELECT count(*) FROM users WHERE id NOT IN (SELECT user_id FROM mines_test_users)").fetchone()[0]
        new=conn.execute("SELECT count(*) FROM users WHERE id NOT IN (SELECT user_id FROM mines_test_users) AND created_at>=? AND created_at<?",(lower,upper)).fetchone()[0]
        today_new=conn.execute("SELECT count(*) FROM users WHERE id NOT IN (SELECT user_id FROM mines_test_users) AND created_at>=?",(today_start,)).fetchone()[0]
        active=conn.execute("SELECT count(DISTINCT user_id) FROM events WHERE user_id NOT IN (SELECT user_id FROM mines_test_users) AND created_at>=? AND created_at<?",(lower,upper)).fetchone()[0]
        daily=allrows(conn,"""SELECT date(created_at,'unixepoch','+8 hours') AS day,count(*) AS registrations FROM users
            WHERE id NOT IN (SELECT user_id FROM mines_test_users) AND created_at>=? AND created_at<? GROUP BY day""",(lower,upper))
        days={r["day"]:r["registrations"] for r in daily}
        trend=[{"day":(start_date+timedelta(days=i)).isoformat(),"registrations":days.get((start_date+timedelta(days=i)).isoformat(),0)}
               for i in range((end_date-start_date).days+1)]
        games=[]
        for game in allrows(conn,"SELECT id,title,status FROM games ORDER BY created_at"):
            gid=game["id"]
            game["first_entries"]=conn.execute("SELECT count(*) FROM profiles WHERE user_id NOT IN (SELECT user_id FROM mines_test_users) AND game_id=? AND first_entered>=? AND first_entered<?",(gid,lower,upper)).fetchone()[0]
            game["active_users"]=conn.execute("SELECT count(DISTINCT user_id) FROM events WHERE user_id NOT IN (SELECT user_id FROM mines_test_users) AND game_id=? AND created_at>=? AND created_at<?",(gid,lower,upper)).fetchone()[0]
            game["room_count"]=conn.execute("SELECT count(*) FROM rooms WHERE host_id NOT IN (SELECT user_id FROM mines_test_users) AND game_id=? AND status='waiting'",(gid,)).fetchone()[0]
            game.update({"matches":None,"play_seconds":None,"game_online":None})
            if gid=="liquid-wars":
                battle=conn.execute("SELECT count(*),coalesce(sum(max(0,min(coalesce(ended_at,?),?)-max(started_at,?))),0) FROM battle_sessions WHERE game_id=? AND started_at<? AND coalesce(ended_at,?)>=?",(time.time(),upper,lower,gid,upper,time.time(),lower)).fetchone()
                game.update({"matches":battle[0],"play_seconds":int(battle[1]),"game_online":sum(len(peers) for rid,peers in request.app.state.relay.rooms.items() if conn.execute("SELECT 1 FROM rooms WHERE id=? AND game_id=?",(rid,gid)).fetchone())})
            elif gid=='mines3d':
                # QA sessions are explicitly marked; never count their matches as player results.
                battle=conn.execute("""SELECT count(*),coalesce(sum(max(0,min(coalesce(ended_at,?),?)-max(created_at,?))),0)
                  FROM mines_matches b WHERE created_at<? AND coalesce(ended_at,?)>=?
                  AND NOT EXISTS(SELECT 1 FROM json_each(b.state,'$.players') j JOIN mines_test_users t ON json_extract(j.value,'$.id')=t.user_id)""",
                  (time.time(),upper,lower,upper,time.time(),lower)).fetchone()
                online_count=conn.execute("SELECT count(DISTINCT m.user_id) FROM members m JOIN rooms r ON r.id=m.room_id WHERE m.game_id='mines3d' AND r.status='playing' AND m.last_seen>? AND m.user_id NOT IN (SELECT user_id FROM mines_test_users)",(time.time()-10,)).fetchone()[0]
                game.update(matches=battle[0],play_seconds=int(battle[1]),game_online=online_count)
            entered={r["day"]:r["n"] for r in allrows(conn,"SELECT date(first_entered,'unixepoch','+8 hours') AS day,count(*) n FROM profiles WHERE user_id NOT IN (SELECT user_id FROM mines_test_users) AND game_id=? AND first_entered>=? AND first_entered<? GROUP BY day",(gid,lower,upper))}
            activity={r["day"]:r["n"] for r in allrows(conn,"SELECT date(created_at,'unixepoch','+8 hours') AS day,count(DISTINCT user_id) n FROM events WHERE user_id NOT IN (SELECT user_id FROM mines_test_users) AND game_id=? AND created_at>=? AND created_at<? GROUP BY day",(gid,lower,upper))}
            game["trend"]=[{"day":day["day"],"first_entries":entered.get(day["day"],0),"active_users":activity.get(day["day"],0)} for day in trend]
            games.append(game)
    return {"total_users":total,"today_new":today_new,"range_new":new,"active_users":active,
            "web_online":len({uid for uid,_ in request.app.state.hub.sockets.values()}),
            "trend":trend,"games":games,"start":start_date.isoformat(),"end":end_date.isoformat(),
            "timezone":"Asia/Shanghai","updated_at":time.time(),
            "definitions":{"registered":"邮箱验证成功后创建的唯一平台账号；管理员也计入。",
                "active":"所选范围内发生注册、登录或游戏接入事件的去重账号；不是持续在线人数。",
                "game_active":"调用游戏进入或房间接入接口的去重账号，包含管理员接入验证；不代表参战。网站浏览、分享及查看邀请不计入。",
                "web_online":"当前持有实时连接的去重账号，可能来自接入验证或客户端；不是游戏在线人数。",
                "gameplay":"Liquid Wars 对局为房主在所有成员连入中继后发起的战斗记录；在线为当前中继连接人数；时长为服务器观察的房间战斗持续时间，不等同于人均游玩时长，不是防作弊战绩。其他游戏未接入时显示待接入。"}}

@router.get("/users")
def users(request:Request,q:str=Query("",max_length=100),page:int=Query(1,ge=1),p=Depends(admin_required)):
    with request.app.state.db.connect() as conn:
        where="%"+q+"%"
        rows=allrows(conn,"SELECT * FROM users WHERE email LIKE ? OR nickname LIKE ? ORDER BY created_at DESC LIMIT 50 OFFSET ?",(where,where,(page-1)*50))
        total=conn.execute("SELECT count(*) FROM users WHERE email LIKE ? OR nickname LIKE ?",(where,where)).fetchone()[0]
    return {"users":rows,"total":total,"page":page}

@router.patch("/users/{user_id}")
async def update_user(user_id:str,body:UserAdminWrite,request:Request,p=Depends(admin_required)):
    effects={"revoke":False,"rooms":[]}
    def change(conn):
        before=rowdict(conn.execute("SELECT * FROM users WHERE id=?",(user_id,)).fetchone())
        if not before:
            fail(404,"USER_NOT_FOUND","用户不存在")
        if user_id==p.user["id"] and (body.role!="admin" or body.status!="active"):
            fail(409,"SELF_LOCKOUT","不能撤销自己当前使用的管理员身份")
        admins=conn.execute("SELECT count(*) FROM users WHERE role='admin' AND status='active'").fetchone()[0]
        if before["role"]=="admin" and before["status"]=="active" and admins<=1 and (body.role!="admin" or body.status!="active"):
            fail(409,"LAST_ADMIN","至少保留一名可用管理员")
        conn.execute("UPDATE users SET nickname=?,role=?,status=? WHERE id=?",(body.nickname,body.role,body.status,user_id))
        effects["rooms"]=allrows(conn,"SELECT r.* FROM rooms r JOIN members m ON m.room_id=r.id WHERE m.user_id=?",(user_id,))
        if body.status!="active" or body.role!=before["role"]:
            effects["revoke"]=True
            conn.execute("DELETE FROM sessions WHERE user_id=?",(user_id,))
            conn.execute("DELETE FROM ws_tickets WHERE user_id=?",(user_id,))
        if body.status!="active":
            for row in effects["rooms"]:
                remove_member(conn,row,user_id)
        after=rowdict(conn.execute("SELECT * FROM users WHERE id=?",(user_id,)).fetchone())
        return {"user":after},before,after
    result=mutation(request,p,body.model_dump(),"user.update",user_id,change)
    if effects["revoke"]:
        await request.app.state.hub.revoke_user(user_id)
    for room in effects["rooms"]:
        await publish_room(request.app,room["id"],[user_id])
    return result

@router.get("/games")
def admin_games(request:Request,p=Depends(admin_required)):
    with request.app.state.db.connect() as conn:
        games=allrows(conn,"SELECT * FROM games ORDER BY created_at")
        for game in games:
            game["releases"]=allrows(conn,"SELECT * FROM releases WHERE game_id=? ORDER BY created_at DESC",(game["id"],))
    return {"games":games}

def write_game(body,request,p,create):
    def change(conn):
        before=rowdict(conn.execute("SELECT * FROM games WHERE id=?",(body.id,)).fetchone())
        if create and before:
            fail(409,"GAME_EXISTS","这个游戏ID已存在")
        if not create and not before:
            fail(404,"GAME_NOT_FOUND","游戏不存在")
        if body.min_players>body.max_players:
            fail(400,"INVALID_CAPACITY","开始人数不能超过房间上限")
        biggest=conn.execute("""SELECT max(n) FROM (SELECT count(*) n FROM members WHERE game_id=? GROUP BY room_id)""",(body.id,)).fetchone()[0] or 0
        if body.max_players<biggest:
            fail(409,"OCCUPIED_CAPACITY","当前房间人数超过新上限，请先处理房间")
        if before:
            conn.execute("UPDATE games SET title=?,tagline=?,description=?,genre=?,status=?,max_players=?,min_players=? WHERE id=?",
                (body.title,body.tagline,body.description,body.genre,body.status,body.max_players,body.min_players,body.id))
        else:
            conn.execute("INSERT INTO games VALUES(?,?,?,?,?,?,?,?,?,?,?)",(body.id,body.id,body.title,body.tagline,body.description,body.genre,body.status,body.max_players,body.min_players,"pending",time.time()))
        after=rowdict(conn.execute("SELECT * FROM games WHERE id=?",(body.id,)).fetchone())
        return {"game":after},before,after
    return mutation(request,p,body.model_dump(),"game.create" if create else "game.update",body.id,change)

@router.post("/games")
def create_game(body:GameWrite,request:Request,p=Depends(admin_required)):
    return write_game(body,request,p,True)

@router.put("/games/{game_id}")
def update_game(game_id:str,body:GameWrite,request:Request,p=Depends(admin_required)):
    if game_id!=body.id:
        fail(400,"IMMUTABLE_GAME_ID","游戏ID不可修改")
    return write_game(body,request,p,False)

@router.post("/games/{game_id}/releases")
def add_release(game_id:str,body:ReleaseWrite,request:Request,p=Depends(admin_required)):
    def change(conn):
        get_game(conn,game_id,False)
        rid=str(uuid.uuid4())
        conn.execute("INSERT INTO releases VALUES(?,?,?,?,?,?,?)",(rid,game_id,body.platform,body.version,body.url,body.notes,time.time()))
        item=rowdict(conn.execute("SELECT * FROM releases WHERE id=?",(rid,)).fetchone())
        return {"release":item},None,item
    return mutation(request,p,body.model_dump(),"release.create",game_id,change)

@router.delete("/releases/{release_id}")
def remove_release(release_id:str,request:Request,p=Depends(admin_required)):
    def change(conn):
        before=rowdict(conn.execute("SELECT * FROM releases WHERE id=?",(release_id,)).fetchone())
        if not before:
            fail(404,"RELEASE_NOT_FOUND","版本记录不存在")
        conn.execute("DELETE FROM releases WHERE id=?",(release_id,))
        return {"ok":True},before,None
    return mutation(request,p,{},"release.remove",release_id,change)

@router.get("/games/{game_id}/profiles")
def game_profiles(game_id:str,request:Request,page:int=Query(1,ge=1),p=Depends(admin_required)):
    with request.app.state.db.connect() as conn:
        get_game(conn,game_id,False)
        profiles=allrows(conn,"SELECT p.*,u.email FROM profiles p JOIN users u ON u.id=p.user_id WHERE game_id=? ORDER BY first_entered DESC LIMIT 50 OFFSET ?",(game_id,(page-1)*50))
        for item in profiles:
            item["data"]=json.loads(item["data"])
        total=conn.execute("SELECT count(*) FROM profiles WHERE game_id=?",(game_id,)).fetchone()[0]
    return {"profiles":profiles,"total":total,"page":page}

@router.put("/games/{game_id}/profiles/{user_id}")
def edit_game_profile(game_id:str,user_id:str,body:GameProfileWrite,request:Request,p=Depends(admin_required)):
    encoded=json.dumps(body.data,ensure_ascii=False)
    if len(encoded)>16000:
        fail(400,"PROFILE_TOO_LARGE","单个游戏资料上限16KB")
    def change(conn):
        before=rowdict(conn.execute("SELECT * FROM profiles WHERE game_id=? AND user_id=?",(game_id,user_id)).fetchone())
        if not before:
            fail(404,"PROFILE_NOT_FOUND","游戏资料不存在")
        conn.execute("UPDATE profiles SET nickname=?,data=? WHERE game_id=? AND user_id=?",(body.nickname,encoded,game_id,user_id))
        after=rowdict(conn.execute("SELECT * FROM profiles WHERE game_id=? AND user_id=?",(game_id,user_id)).fetchone())
        return {"profile":after},before,after
    return mutation(request,p,body.model_dump(),"game.profile.update",game_id+":"+user_id,change)

@router.get("/settings")
def get_settings(request:Request,p=Depends(admin_required)):
    with request.app.state.db.connect() as conn:
        return {"settings":setting_values(conn)}

@router.put("/settings")
def put_settings(body:SettingsWrite,request:Request,p=Depends(admin_required)):
    def change(conn):
        before=setting_values(conn)
        for k,v in body.model_dump().items():
            conn.execute("UPDATE settings SET value=? WHERE key=?",(json.dumps(v,ensure_ascii=False),k))
        return {"settings":body.model_dump()},before,body.model_dump()
    return mutation(request,p,body.model_dump(),"settings.update","site",change)

@router.get("/rooms")
def admin_rooms(request:Request,p=Depends(admin_required)):
    with request.app.state.db.connect() as conn:
        return {"rooms":allrows(conn,"""SELECT r.*,g.title AS game_title,(SELECT count(*) FROM members m WHERE m.room_id=r.id) AS member_count
            FROM rooms r JOIN games g ON g.id=r.game_id ORDER BY created_at DESC LIMIT 100""")}

@router.post("/rooms/{code}/close")
async def close_room(code:str,request:Request,p=Depends(admin_required)):
    targets=[]
    def change(conn):
        before=get_room(conn,code)
        targets.extend(r[0] for r in conn.execute("SELECT user_id FROM members WHERE room_id=?",(before["id"],)))
        if before['game_id']=='mines3d':
            from . import mines, mines_engine
            match=mines.load_match(conn,before)
            if match and match['ended'] is None:
                mines_engine.finish(match,[],'room_closed',time.time())
                match['version']+=1
                mines.save_match(conn,before,match)
        conn.execute("DELETE FROM members WHERE room_id=?",(before["id"],))
        conn.execute("UPDATE rooms SET status='closed',updated_at=? WHERE id=?",(time.time(),before["id"]))
        return {"ok":True,"room_id":before["id"]},before,{"status":"closed"}
    result=mutation(request,p,{},"room.close",code,change)
    await publish_room(request.app,result["room_id"],targets)
    return result

@router.get("/emotes")
def admin_emotes(request:Request,p=Depends(admin_required)):
    with request.app.state.db.connect() as conn:
        return {"emotes":allrows(conn,"SELECT * FROM emotes ORDER BY cell")}

@router.put("/emotes/{emote_id}")
def update_emote(emote_id:str,body:EmoteAdminWrite,request:Request,p=Depends(admin_required)):
    def change(conn):
        before=rowdict(conn.execute("SELECT * FROM emotes WHERE id=?",(emote_id,)).fetchone())
        if not before:
            fail(404,"EMOTE_NOT_FOUND","表情不存在")
        conn.execute("UPDATE emotes SET label=?,enabled=? WHERE id=?",(body.label,int(body.enabled),emote_id))
        return {"ok":True},before,body.model_dump()
    return mutation(request,p,body.model_dump(),"emote.update",emote_id,change)

@router.get("/keys")
def keys(request:Request,p=Depends(admin_required)):
    with request.app.state.db.connect() as conn:
        return {"keys":[serialize_key(r) for r in conn.execute("SELECT * FROM api_keys ORDER BY created_at DESC")]}

@router.post("/keys")
def create_key(body:KeyCreate,request:Request,p=Depends(admin_required)):
    def change(conn):
        token=new_key()
        kid=str(uuid.uuid4())
        now=time.time()
        conn.execute("INSERT INTO api_keys VALUES(?,?,?,?,?,?,?,?,NULL,NULL)",(kid,body.name,digest(token),token[:12],body.scope,p.user["id"],now,now+body.expires_days*86400))
        info=serialize_key(conn.execute("SELECT * FROM api_keys WHERE id=?",(kid,)).fetchone())
        return {"key":info,"token":token},None,info
    return mutation(request,p,body.model_dump(),"key.create",body.name,change,True)

@router.post("/keys/{key_id}/revoke")
def revoke_key(key_id:str,request:Request,p=Depends(admin_required)):
    def change(conn):
        before=conn.execute("SELECT * FROM api_keys WHERE id=?",(key_id,)).fetchone()
        if not before:
            fail(404,"KEY_NOT_FOUND","凭证不存在")
        conn.execute("UPDATE api_keys SET revoked_at=? WHERE id=?",(time.time(),key_id))
        return {"ok":True},serialize_key(before),{"revoked":True}
    return mutation(request,p,{},"key.revoke",key_id,change)

@router.post("/keys/{key_id}/rotate")
def rotate_key(key_id:str,request:Request,p=Depends(admin_required)):
    def change(conn):
        old=conn.execute("SELECT * FROM api_keys WHERE id=?",(key_id,)).fetchone()
        if not old or old["revoked_at"]:
            fail(404,"KEY_NOT_FOUND","凭证不存在或已撤销")
        token=new_key()
        conn.execute("UPDATE api_keys SET token_hash=?,prefix=?,last_used=NULL WHERE id=?",(digest(token),token[:12],key_id))
        after=serialize_key(conn.execute("SELECT * FROM api_keys WHERE id=?",(key_id,)).fetchone())
        return {"key":after,"token":token},serialize_key(old),after
    return mutation(request,p,{},"key.rotate",key_id,change,True)

@router.get("/audit")
def get_audit(request:Request,page:int=Query(1,ge=1),p=Depends(admin_required)):
    with request.app.state.db.connect() as conn:
        return {"entries":allrows(conn,"SELECT * FROM audit ORDER BY id DESC LIMIT 50 OFFSET ?",((page-1)*50,)),
                "total":conn.execute("SELECT count(*) FROM audit").fetchone()[0],"page":page}

@router.get("/requests")
def api_requests(request:Request,page:int=Query(1,ge=1),p=Depends(admin_required)):
    with request.app.state.db.connect() as conn:
        return {"entries":allrows(conn,"SELECT * FROM api_requests ORDER BY id DESC LIMIT 50 OFFSET ?",((page-1)*50,)),
                "total":conn.execute("SELECT count(*) FROM api_requests").fetchone()[0],"page":page}

@router.get("/integration-lab")
def integration_lab(request:Request,p=Depends(admin_required)):
    if request.app.state.config.env!="development":
        fail(404,"LAB_DISABLED","接入验证仅在本地开发环境开放")
    return {"enabled":True,"battle":"pending","matchmaking":"pending","purpose":"客户端接入验证；不作为玩家游玩入口"}
