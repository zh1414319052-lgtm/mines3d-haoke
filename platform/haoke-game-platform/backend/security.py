import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from fastapi import HTTPException, Request
from fastapi.security import APIKeyCookie, HTTPBearer
from .db import rowdict

cookie_scheme = APIKeyCookie(name="hk_session", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)

def fail(status, code, message):
    raise HTTPException(status_code=status, detail={"code": code, "message": message})

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def otp_digest(secret, cid, code):
    return hmac.new(secret.encode(), (cid + ":" + code).encode(), hashlib.sha256).hexdigest()

@dataclass
class Principal:
    user: dict
    actor: str
    session_hash: str = ""
    csrf: str = ""
    scope: str = ""
    key_id: str = ""

def authenticate(request: Request, optional=False):
    authorization = request.headers.get("authorization", "")
    bearer = authorization[7:] if authorization.startswith("Bearer ") else ""
    cookie = request.cookies.get("hk_session", "")
    token = bearer or cookie
    if not token:
        if optional:
            return None
        fail(401, "LOGIN_REQUIRED", "请先登录")
    db = request.app.state.db
    with db.connect(write=True) as conn:
        if bearer.startswith("hkai_"):
            row = conn.execute("""SELECT k.*,u.role,u.status,u.email,u.nickname,u.avatar
                FROM api_keys k JOIN users u ON u.id=k.created_by
                WHERE k.token_hash=?""", (digest(bearer),)).fetchone()
            if row:
                request.state.actor = "key:"+row["id"]
            if not row or row["revoked_at"] or row["expires_at"]<=time.time() or row["status"] != "active" or row["role"] != "admin":
                fail(401,"INVALID_KEY","授权凭证无效、已撤销或已过期")
            conn.execute("UPDATE api_keys SET last_used=? WHERE id=?", (time.time(),row["id"]))
            return Principal({"id":row["created_by"],"role":"admin","status":"active","email":row["email"]},
                "key:"+row["id"], scope=row["scope"], key_id=row["id"])
        session = conn.execute("SELECT * FROM sessions WHERE token_hash=? AND expires_at>?", (digest(token),time.time())).fetchone()
        if not session or (bearer and session["kind"] != "native") or (not bearer and session["kind"] != "web"):
            if optional:
                return None
            fail(401,"SESSION_EXPIRED","登录已失效，请重新登录")
        user = rowdict(conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone())
        request.state.actor = "user:"+session["user_id"]
        if not user or user["status"] != "active":
            fail(403,"ACCOUNT_DISABLED","账号已暂停使用")
        if not bearer and request.method not in ("GET","HEAD","OPTIONS"):
            supplied = request.headers.get("x-csrf-token","")
            if not supplied or not hmac.compare_digest(supplied,session["csrf"]):
                fail(403,"CSRF_REQUIRED","页面验证已失效，请刷新后重试")
        return Principal(user, "user:"+user["id"], session_hash=digest(token), csrf=session["csrf"])

def user_required(request: Request):
    principal = authenticate(request)
    if principal.key_id:
        fail(403,"PLAYER_SESSION_REQUIRED","管理凭证不能冒充玩家加入房间")
    return principal

def admin_required(request: Request):
    principal = authenticate(request)
    if principal.user["role"] != "admin":
        fail(403,"ADMIN_REQUIRED","仅管理员可以访问")
    if principal.key_id and request.method not in ("GET","HEAD") and principal.scope != "admin:full":
        fail(403,"READ_ONLY_KEY","当前凭证仅有读取权限")
    return principal

def audit(conn, actor, action, target, before, after, request_id):
    conn.execute("INSERT INTO audit(actor,action,target,before_json,after_json,created_at,request_id) VALUES(?,?,?,?,?,?,?)",
        (actor,action,target,json.dumps(before,ensure_ascii=False) if before is not None else None,
         json.dumps(after,ensure_ascii=False) if after is not None else None,time.time(),request_id))

def mutation(request, principal, payload, action, target, callback, redact_result=False):
    """All admin writes share authorization, transaction, idempotency and audit paths."""
    key = request.headers.get("idempotency-key","")
    if not 8 <= len(key) <= 128:
        fail(400,"IDEMPOTENCY_REQUIRED","写入请求需要8–128位 Idempotency-Key")
    signature = digest(request.method + request.url.path + json.dumps(payload,sort_keys=True,ensure_ascii=False))
    with request.app.state.db.connect(write=True) as conn:
        cached = conn.execute("SELECT * FROM idempotency WHERE actor=? AND key=?", (principal.actor,key)).fetchone()
        if cached:
            if cached["signature"] != signature:
                fail(409,"IDEMPOTENCY_CONFLICT","同一幂等键不能用于不同操作")
            return json.loads(cached["response"])
        result, before, after = callback(conn)
        audit(conn,principal.actor,action,target,before,after,request.state.request_id)
        saved = {**result, "token": None, "secret_shown_once": True} if redact_result else result
        conn.execute("INSERT INTO idempotency VALUES(?,?,?,?,?)",
            (principal.actor,key,signature,json.dumps(saved,ensure_ascii=False),time.time()))
        return result

def new_key():
    return "hkai_" + secrets.token_urlsafe(40)
