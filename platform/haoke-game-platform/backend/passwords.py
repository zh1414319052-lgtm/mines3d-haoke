"""Email-proved password setup/reset; credential material never joins public users.

scrypt 2^15/r8/p3 per OWASP Password Storage Cheat Sheet; stdlib OpenSSL backend.
"""
import asyncio
import hashlib
import hmac
import secrets
import time
from typing import Literal
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .models import CodeRequest
from .db import rowdict
from .security import audit, digest, fail, otp_digest

SCHEMA = """
CREATE TABLE IF NOT EXISTS passwords(
 user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 encoded TEXT NOT NULL, changed_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS password_attempts(
 id INTEGER PRIMARY KEY AUTOINCREMENT, mailbox TEXT NOT NULL, ip TEXT NOT NULL,
 created_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS password_attempt_time ON password_attempts(created_at);
CREATE INDEX IF NOT EXISTS password_attempt_mail ON password_attempts(mailbox,created_at);
"""
router=APIRouter(prefix='/api/auth/password',tags=['账号'])

class PasswordLogin(BaseModel):
    model_config=ConfigDict(extra='forbid') # Never strip or normalize a password.
    email: str=Field(min_length=3,max_length=254)
    password: str=Field(min_length=1,max_length=128)
    client: Literal['web','native']='web'
    @field_validator('email')
    @classmethod
    def email_valid(cls,value): return CodeRequest(email=value).email

class PasswordReset(BaseModel):
    model_config=ConfigDict(extra='forbid')
    challenge_id: str=Field(min_length=20,max_length=100)
    code: str=Field(pattern=r'^[0-9]{6}$')
    password: str=Field(min_length=10,max_length=128)
    client: Literal['web','native']='web'
    @field_validator('password')
    @classmethod
    def password_valid(cls,value):
        if not value.strip() or any(ord(c)<32 for c in value):
            raise ValueError('密码不能全部为空白或包含控制字符')
        return value

def derive(password,salt):
    return hashlib.scrypt(password.encode('utf-8'),salt=salt,n=32768,r=8,p=3,maxmem=64*1024*1024,dklen=32)

def encode(password):
    salt=secrets.token_bytes(16)
    return 'scrypt-v1$'+salt.hex()+'$'+derive(password,salt).hex()

def matches(password,encoded):
    try:
        version,salt,wanted=encoded.split('$')
        if version!='scrypt-v1' or len(salt)!=32 or len(wanted)!=64:return False
        return hmac.compare_digest(derive(password,bytes.fromhex(salt)).hex(),wanted)
    except (ValueError,TypeError):return False

def issue(conn,user,client,cfg,now):
    token,csrf=secrets.token_urlsafe(40),secrets.token_urlsafe(32)
    conn.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?)',(digest(token),user['id'],csrf,client,now,now+cfg.session_seconds))
    conn.execute('UPDATE users SET last_login=? WHERE id=?',(now,user['id']))
    conn.execute("INSERT INTO events(user_id,kind,created_at) VALUES(?,'login',?)",(user['id'],now))
    user={**user,'last_login':now,'has_password':True}
    return token,{'user':user,'is_new':False,'csrf':csrf if client=='web' else None,'expires_at':now+cfg.session_seconds}

def deliver(response,token,result,client,cfg):
    if client=='web':
        response.set_cookie('hk_session',token,max_age=cfg.session_seconds,httponly=True,secure=cfg.env=='production',samesite='lax',path='/')
    else:result.update(access_token=token,token_type='Bearer')
    return result

@router.post('/login')
async def login(body:PasswordLogin,request:Request,response:Response):
    cfg,db=request.app.state.config,request.app.state.db
    now=time.time(); mailbox=otp_digest(cfg.secret,'password-rate',body.email); ip=request.client.host
    # Reserve attempts atomically before expensive work, including concurrent requests.
    with db.connect(write=True) as conn:
        conn.execute('DELETE FROM password_attempts WHERE created_at<?',(now-900,))
        count=conn.execute('SELECT count(*) FROM password_attempts WHERE mailbox=?',(mailbox,)).fetchone()[0]
        ip_count=conn.execute('SELECT count(*) FROM password_attempts WHERE ip=?',(ip,)).fetchone()[0]
        if count>=8 or ip_count>=40:fail(429,'PASSWORD_RATE_LIMIT','尝试过于频繁，请15分钟后重试，或使用邮箱验证码登录')
        cursor=conn.execute('INSERT INTO password_attempts(mailbox,ip,created_at) VALUES(?,?,?)',(mailbox,ip,now)); attempt=cursor.lastrowid
        user=rowdict(conn.execute('SELECT * FROM users WHERE email=?',(body.email,)).fetchone())
        saved=conn.execute('SELECT encoded FROM passwords WHERE user_id=?',(user['id'] if user else '',)).fetchone()
        encoded=saved['encoded'] if saved else 'scrypt-v1$'+'00'*16+'$'+'00'*32
    async with request.app.state.password_slots:
        good=await asyncio.to_thread(matches,body.password,encoded)
    with db.connect(write=True) as conn:
        # A reset/disable racing this verification must not issue an old-password session.
        current=conn.execute('SELECT encoded FROM passwords WHERE user_id=?',(user['id'] if user else '',)).fetchone()
        active=conn.execute('SELECT status FROM users WHERE id=?',(user['id'] if user else '',)).fetchone()
        if not good or not user or not current or current['encoded']!=encoded or not active or active['status']!='active':
            error=True
        else:
            error=False; token,result=issue(conn,user,body.client,cfg,time.time())
            conn.execute('DELETE FROM password_attempts WHERE id=?',(attempt,))
    if error:fail(400,'INVALID_CREDENTIALS','邮箱或密码不正确；未设置密码可用邮箱验证码登录')
    return deliver(response,token,result,body.client,cfg)

@router.post('/reset')
async def reset(body:PasswordReset,request:Request,response:Response):
    cfg,db=request.app.state.config,request.app.state.db
    error=None
    # Verify and consume the one-time challenge BEFORE allocating KDF work.
    with db.connect(write=True) as conn:
        ch=conn.execute('SELECT * FROM challenges WHERE id=?',(body.challenge_id,)).fetchone()
        if not ch or ch['purpose']!='password' or ch['consumed'] or ch['expires_at']<=time.time() or ch['attempts']>=5:
            error=('CODE_EXPIRED','请重新获取设置密码专用验证码')
        elif not hmac.compare_digest(ch['digest'],otp_digest(cfg.secret,body.challenge_id,body.code)):
            conn.execute('UPDATE challenges SET attempts=attempts+1 WHERE id=?',(body.challenge_id,))
            error=('CODE_INCORRECT','验证码不正确；最多尝试5次')
        else:
            user=rowdict(conn.execute('SELECT * FROM users WHERE email=?',(ch['email'],)).fetchone())
            if not user:error=('ACCOUNT_NOT_FOUND','此邮箱尚未注册，请先用验证码登录注册')
            elif user['status']!='active':error=('ACCOUNT_DISABLED','账号已暂停使用')
            if not error:conn.execute('UPDATE challenges SET consumed=1,dev_code=NULL WHERE id=?',(body.challenge_id,))
    if error:fail(400,*error)
    async with request.app.state.password_slots:
        encoded=await asyncio.to_thread(encode,body.password)
    with db.connect(write=True) as conn:
        # A later challenge or password change wins over an older request in flight.
        later=conn.execute('SELECT 1 FROM challenges WHERE email=? AND created_at>?',(user['email'],ch['created_at'])).fetchone()
        active=conn.execute('SELECT status FROM users WHERE id=?',(user['id'],)).fetchone()
        if later or not active or active['status']!='active':fail(400,'CODE_EXPIRED','请求已更新，请重新验证邮箱')
        now=time.time()
        conn.execute('INSERT INTO passwords VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET encoded=excluded.encoded,changed_at=excluded.changed_at',(user['id'],encoded,now))
        conn.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))
        conn.execute('DELETE FROM ws_tickets WHERE user_id=?',(user['id'],))
        conn.execute('DELETE FROM password_attempts WHERE mailbox=?',(otp_digest(cfg.secret,'password-rate',user['email']),))
        conn.execute('UPDATE challenges SET consumed=1,dev_code=NULL WHERE email=?',(user['email'],))
        audit(conn,'user:'+user['id'],'password.reset',user['id'],None,{'sessions_revoked':True},request.state.request_id)
        token,result=issue(conn,user,body.client,cfg,now)
    await request.app.state.hub.revoke_user(user['id'])
    return deliver(response,token,result,body.client,cfg)
