import asyncio
import hmac
import ipaddress
import secrets
import smtplib
import ssl
import time
import uuid
from email.message import EmailMessage
from fastapi import APIRouter, Depends, Request, Response
from .db import allrows, rowdict
from .models import CodeRequest, CodeVerify, ProfileUpdate
from .security import authenticate, audit, digest, fail, otp_digest, user_required

router = APIRouter(prefix="/api",tags=["账号"])

def loopback(request):
    try:
        return ipaddress.ip_address(request.client.host).is_loopback
    except ValueError:
        return False

def smtp_send(config,email,code):
    msg = EmailMessage()
    msg["Subject"] = "浩科游戏中心 · 邮箱验证码"
    msg["From"] = config.smtp_from
    msg["To"] = email
    msg.set_content(f"你的验证码是：{code}\n有效期10分钟，请勿向他人透露。\n如果不是你本人操作，请忽略此邮件。")
    context = ssl.create_default_context()
    if config.smtp_security == "ssl":
        server = smtplib.SMTP_SSL(config.smtp_host,config.smtp_port,context=context,timeout=15)
    else:
        server = smtplib.SMTP(config.smtp_host,config.smtp_port,timeout=15)
    with server:
        if config.smtp_security == "starttls":
            server.starttls(context=context)
        elif config.smtp_security != "ssl":
            raise RuntimeError("SMTP requires TLS.")
        if config.smtp_user:
            server.login(config.smtp_user,config.smtp_password)
        server.send_message(msg)

@router.post("/auth/code")
async def request_code(body: CodeRequest, request: Request):
    cfg = request.app.state.config
    now = time.time()
    cid, code = secrets.token_urlsafe(24), f"{secrets.randbelow(1000000):06}"
    ip = request.client.host
    with request.app.state.db.connect(write=True) as conn:
        recent = conn.execute("SELECT created_at FROM challenges WHERE email=? ORDER BY created_at DESC LIMIT 1",(body.email,)).fetchone()
        if recent and now-recent["created_at"]<cfg.otp_cooldown:
            fail(429,"CODE_COOLDOWN","请稍等60秒再获取验证码")
        if conn.execute("SELECT count(*) FROM challenges WHERE ip=? AND created_at>?",(ip,now-900)).fetchone()[0]>=20:
            fail(429,"TOO_MANY_REQUESTS","请求过于频繁，请15分钟后再试")
        # Creating a new challenge supersedes older codes for the same mailbox.
        conn.execute("UPDATE challenges SET consumed=1,dev_code=NULL WHERE email=? AND consumed=0",(body.email,))
        conn.execute("INSERT INTO challenges(id,email,digest,purpose,created_at,expires_at,ip,dev_code) VALUES(?,?,?,?,?,?,?,?)",
            (cid,body.email,otp_digest(cfg.secret,cid,code),body.purpose,now,now+600,ip,code if cfg.mail_mode=="development" else None))
    if cfg.mail_mode == "smtp":
        try:
            await asyncio.to_thread(smtp_send,cfg,body.email,code)
        except Exception:
            with request.app.state.db.connect(write=True) as conn:
                conn.execute("UPDATE challenges SET consumed=1,dev_code=NULL WHERE id=?",(cid,))
            fail(503,"MAIL_UNAVAILABLE","邮件服务暂不可用，请稍后重试")
    return {"challenge_id":cid,"expires_in":600,"retry_after":cfg.otp_cooldown,
            "delivery":"development" if cfg.mail_mode=="development" else "email",
            "dev_mailbox_available": cfg.env=="development" and cfg.mail_mode=="development" and loopback(request)}

@router.get("/dev/mailbox",tags=["本地开发"])
def dev_mailbox(request: Request, challenge_id: str):
    cfg = request.app.state.config
    if cfg.env!="development" or cfg.mail_mode!="development" or not loopback(request):
        fail(404,"NOT_FOUND","此入口不可用")
    with request.app.state.db.connect() as conn:
        row = conn.execute("SELECT email,dev_code,expires_at FROM challenges WHERE id=? AND consumed=0 AND expires_at>?",(challenge_id,time.time())).fetchone()
        if not row:
            fail(404,"CODE_UNAVAILABLE","验证码已使用或失效，请重新获取")
        return {"email":row["email"],"code":row["dev_code"],"expires_at":row["expires_at"],"development_only":True}

@router.post("/auth/verify")
async def verify(body: CodeVerify, request: Request, response: Response):
    cfg, db = request.app.state.config, request.app.state.db
    error = None
    result = None
    token, csrf = secrets.token_urlsafe(40), secrets.token_urlsafe(32)
    now = time.time()
    with db.connect(write=True) as conn:
        ch = conn.execute("SELECT * FROM challenges WHERE id=?",(body.challenge_id,)).fetchone()
        if not ch or ch["purpose"] not in ("signin","recovery") or ch["consumed"] or ch["expires_at"]<now or ch["attempts"]>=5:
            error = ("CODE_EXPIRED","验证码已使用或失效，请重新获取")
        elif not hmac.compare_digest(ch["digest"],otp_digest(cfg.secret,body.challenge_id,body.code)):
            conn.execute("UPDATE challenges SET attempts=attempts+1 WHERE id=?",(body.challenge_id,))
            error = ("CODE_INCORRECT","验证码不正确；最多尝试5次")
        else:
            conn.execute("UPDATE challenges SET consumed=1,dev_code=NULL WHERE id=?",(body.challenge_id,))
            user = rowdict(conn.execute("SELECT * FROM users WHERE email=?",(ch["email"],)).fetchone())
            if user and user["status"]!="active":
                error = ("ACCOUNT_DISABLED","账号已暂停使用")
            elif not user and ch["purpose"]=="recovery":
                error = ("ACCOUNT_NOT_FOUND","此邮箱尚未注册，请使用注册登录入口")
            else:
                is_new = not user
                if is_new:
                    uid = str(uuid.uuid4())
                    role = "admin" if ch["email"]==cfg.admin_email else "user"
                    conn.execute("INSERT INTO users VALUES(?,?,?,?,?,?,?,?)",(uid,ch["email"],"玩家"+uid[:4],0,role,"active",now,now))
                    conn.execute("INSERT INTO events(user_id,kind,created_at) VALUES(?,'register',?)",(uid,now))
                    user = rowdict(conn.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone())
                else:
                    conn.execute("UPDATE users SET last_login=? WHERE id=?",(now,user["id"]))
                if ch["purpose"]=="recovery":
                    conn.execute("DELETE FROM sessions WHERE user_id=?",(user["id"],))
                    conn.execute("DELETE FROM ws_tickets WHERE user_id=?",(user["id"],))
                    audit(conn,"user:"+user["id"],"account.recover",user["id"],None,{"sessions_revoked":True},request.state.request_id)
                conn.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?)",(digest(token),user["id"],csrf,body.client,now,now+cfg.session_seconds))
                conn.execute("INSERT INTO events(user_id,kind,created_at) VALUES(?,'login',?)",(user["id"],now))
                result={"user":user,"is_new":is_new,"csrf":csrf if body.client=="web" else None,"expires_at":now+cfg.session_seconds}
    if error:
        fail(400,*error)
    if ch["purpose"]=="recovery":
        await request.app.state.hub.revoke_user(user["id"])
    if body.client=="web":
        response.set_cookie("hk_session",token,max_age=cfg.session_seconds,httponly=True,
                            secure=cfg.env=="production",samesite="lax",path="/")
    else:
        result["access_token"]=token
        result["token_type"]="Bearer"
    return result

@router.get("/me")
def me(request: Request):
    p = authenticate(request,optional=True)
    if not p:
        return {"user":None,"csrf":None}
    if p.key_id:
        fail(403,"PLAYER_SESSION_REQUIRED","此接口使用玩家登录会话")
    with request.app.state.db.connect() as conn:
        profiles=allrows(conn,"SELECT p.*,g.title FROM profiles p JOIN games g ON g.id=p.game_id WHERE user_id=?",(p.user["id"],))
        rooms=allrows(conn,"SELECT r.* FROM rooms r JOIN members m ON r.id=m.room_id WHERE m.user_id=? AND r.status IN ('waiting','playing')",(p.user["id"],))
        mutes=[r[0] for r in conn.execute("SELECT target_id FROM mutes WHERE user_id=?",(p.user["id"],))]
        has_password=conn.execute("SELECT 1 FROM passwords WHERE user_id=?",(p.user["id"],)).fetchone() is not None
    return {"user":{**p.user,"has_password":has_password},"csrf":p.csrf,"profiles":profiles,"rooms":rooms,"mutes":mutes}

@router.patch("/me")
def update_profile(body:ProfileUpdate,request:Request,p=Depends(user_required)):
    with request.app.state.db.connect(write=True) as conn:
        conn.execute("UPDATE users SET nickname=?,avatar=? WHERE id=?",(body.nickname,body.avatar,p.user["id"]))
        return {"user":rowdict(conn.execute("SELECT * FROM users WHERE id=?",(p.user["id"],)).fetchone())}

@router.post("/auth/logout")
async def logout(request:Request,response:Response,p=Depends(user_required)):
    with request.app.state.db.connect(write=True) as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash=?",(p.session_hash,))
        conn.execute("DELETE FROM ws_tickets WHERE session_hash=?",(p.session_hash,))
    await request.app.state.hub.revoke_session(p.session_hash)
    response.delete_cookie("hk_session",path="/")
    return {"ok":True}

@router.post("/auth/revoke-sessions")
async def revoke_sessions(request:Request,response:Response,p=Depends(user_required)):
    with request.app.state.db.connect(write=True) as conn:
        conn.execute("DELETE FROM sessions WHERE user_id=?",(p.user["id"],))
        conn.execute("DELETE FROM ws_tickets WHERE user_id=?",(p.user["id"],))
        audit(conn,p.actor,"sessions.revoke",p.user["id"],None,{"all":True},request.state.request_id)
    await request.app.state.hub.revoke_user(p.user["id"])
    response.delete_cookie("hk_session",path="/")
    return {"ok":True}
