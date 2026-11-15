import asyncio
from contextlib import asynccontextmanager, suppress
import json
from pathlib import Path
import secrets
import sqlite3
import time
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.openapi.utils import get_openapi
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .config import ROOT, Settings, from_env
from .db import Database, allrows, setting_values
from . import auth, rooms, admin, online, passwords, mines

def create_app(config:Settings|None=None):
    cfg=config or from_env()
    cfg.prepare()
    db=Database(cfg.data_dir/"platform.sqlite3")
    db.initialize()
    with db.connect() as conn:
        conn.executescript(passwords.SCHEMA)
        conn.execute("INSERT OR IGNORE INTO migrations VALUES(6,?)", (time.time(),))
    with db.connect() as conn:
        conn.executescript(online.SCHEMA)
        conn.execute("INSERT OR IGNORE INTO migrations VALUES(3,?)", (time.time(),))
        if not conn.execute("SELECT 1 FROM migrations WHERE version=4").fetchone():
            conn.execute("UPDATE games SET min_players=1 WHERE id='liquid-wars'")
            conn.execute("INSERT INTO migrations VALUES(4,?)", (time.time(),))
        if not conn.execute("SELECT 1 FROM migrations WHERE version=5").fetchone():
            conn.execute("UPDATE games SET integration='host-relay' WHERE id='liquid-wars'")
            previous=json.dumps("一个账号，连接不同游戏。网站负责发现与分享，组队和匹配将在游戏内完成；Liquid Wars 联网接入准备中。",ensure_ascii=False)
            announcement=json.dumps("液态战争 Android 联网测试版：游戏内匹配与好友房，最多6名真人；等待8秒后空位补电脑，单人也能开局。",ensure_ascii=False)
            conn.execute("UPDATE settings SET value=? WHERE key='announcement' AND value=?",(announcement,previous))
            conn.execute("INSERT INTO migrations VALUES(5,?)", (time.time(),))
    with db.connect() as conn:
        mines.initialize(conn,time.time())

    @asynccontextmanager
    async def lifespan(app):
        # A restarted process has no live sockets; existing players get a fresh grace window.
        with db.connect(write=True) as conn:
            conn.execute("UPDATE battle_sessions SET ended_at=?,reason='server_restart' WHERE ended_at IS NULL", (time.time(),))
            conn.execute("DELETE FROM members WHERE room_id IN (SELECT id FROM rooms WHERE status='playing' AND game_id!='mines3d')")
            conn.execute("UPDATE rooms SET status='closed' WHERE status='playing' AND game_id!='mines3d'")
            conn.execute("DELETE FROM match_queue")
            conn.execute("UPDATE members SET ready=0,last_seen=?",(time.time(),))
        task=asyncio.create_task(rooms.sweeper(app))
        mines_task=asyncio.create_task(mines.sweeper(app))
        yield
        task.cancel()
        mines_task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        with suppress(asyncio.CancelledError):
            await mines_task
        for ws in list(app.state.hub.sockets):
            with suppress(Exception):
                await ws.close(code=1001)
        for rid in list(app.state.relay.rooms):
            await app.state.relay.close_room(rid, "server_shutdown")

    app=FastAPI(title="浩科游戏中心 API",version="0.5.0",description="统一账号与多游戏管理。Liquid Wars 主机中继；Mines3D 服务器权威合作与猎雷。网站负责发现、账号和分享。",
                lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url="/api/openapi.json")
    app.state.config=cfg
    app.state.db=db
    app.state.password_slots=asyncio.Semaphore(2)
    app.state.hub=rooms.Hub()
    app.state.relay=online.RelayHub(app)
    app.state.hub.relay=app.state.relay
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=cfg.allowed_hosts)

    @app.middleware("http")
    async def protection(request:Request,call_next):
        request.state.request_id=secrets.token_hex(12)
        if request.method not in ("GET","HEAD","OPTIONS"):
            origin=request.headers.get("origin")
            if origin and origin not in cfg.allowed_origins:
                return JSONResponse({"error":{"code":"ORIGIN_REJECTED","message":"请求来源不受信任"}},status_code=403)
            if request.headers.get("content-type","").split(";")[0] not in ("application/json","") and request.url.path.startswith("/api"):
                return JSONResponse({"error":{"code":"JSON_REQUIRED","message":"请使用 JSON 请求"}},status_code=415)
            try:
                if int(request.headers.get("content-length","0"))>32768:
                    return JSONResponse({"error":{"code":"BODY_TOO_LARGE","message":"请求内容过大"}},status_code=413)
            except ValueError:
                return JSONResponse({"error":{"code":"INVALID_LENGTH","message":"请求格式错误"}},status_code=400)
            raw=await request.body()
            if len(raw)>32768:
                return JSONResponse({"error":{"code":"BODY_TOO_LARGE","message":"请求内容过大"}},status_code=413)
        response=await call_next(request)
        response.headers["X-Request-ID"]=request.state.request_id
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["X-Frame-Options"]="SAMEORIGIN"
        response.headers["Referrer-Policy"]="same-origin"
        response.headers["Permissions-Policy"]="camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'self'; base-uri 'self'; object-src 'none'"
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"]="no-store"
        if cfg.env=="production":
            response.headers["Strict-Transport-Security"]="max-age=31536000"
        return response

    @app.middleware("http")
    async def log_admin_call(request:Request,call_next):
        response=await call_next(request)
        if request.url.path.startswith("/api/admin/"):
            with db.connect(write=True) as conn:
                conn.execute("INSERT INTO api_requests(actor,method,path,status,created_at,request_id) VALUES(?,?,?,?,?,?)",
                    (getattr(request.state,"actor","anonymous"),request.method,request.url.path,response.status_code,
                     time.time(),getattr(request.state,"request_id","unknown")))
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request,exc):
        detail=exc.detail if isinstance(exc.detail,dict) else {"code":"REQUEST_FAILED","message":str(exc.detail)}
        return JSONResponse({"error":detail},status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc):
        fields=[{"field":".".join(str(p) for p in e["loc"][1:]),"message":e["msg"]} for e in exc.errors()]
        return JSONResponse({"error":{"code":"VALIDATION_ERROR","message":"请检查输入内容","fields":fields}},status_code=422)

    @app.exception_handler(sqlite3.OperationalError)
    async def db_error(request,exc):
        return JSONResponse({"error":{"code":"DATABASE_BUSY","message":"数据服务忙，请稍后重试"}},status_code=503)

    app.include_router(auth.router)
    app.include_router(passwords.router)
    app.include_router(rooms.router)
    app.include_router(admin.router)
    app.include_router(online.router)
    app.include_router(mines.router)

    def openapi_schema():
        if app.openapi_schema:
            return app.openapi_schema
        schema=get_openapi(title=app.title,version=app.version,description=app.description,routes=app.routes)
        schema.setdefault("components",{})["securitySchemes"]={
            "PlayerOrAdminBearer":{"type":"http","scheme":"bearer","description":"原生玩家会话或独立 AI 管理凭证；完整管理凭证以 hkai_ 开头。"},
            "WebSession":{"type":"apiKey","in":"cookie","name":"hk_session","description":"浏览器 HttpOnly Cookie。所有已登录的写请求还须 X-CSRF-Token（从 /api/me 获取）。"}}
        public={"/api/health","/api/config","/api/games","/api/games/{game_id}","/api/auth/code","/api/auth/verify","/api/auth/password/login","/api/auth/password/reset","/api/dev/mailbox","/api/invitations/{code}","/api/rooms"}
        for path,methods in schema["paths"].items():
            for method,operation in methods.items():
                if method not in {"get","post","put","patch","delete"}:
                    continue
                anonymous=path in public and (method=="get" or path in {"/api/auth/code","/api/auth/verify","/api/auth/password/login","/api/auth/password/reset"})
                if not anonymous:
                    operation["security"]=[{"PlayerOrAdminBearer":[]},{"WebSession":[]}]+([{}] if path=="/api/me" and method=="get" else [])
                if method not in {"get","head"} and operation.get("security"):
                    operation.setdefault("parameters",[]).append({"name":"X-CSRF-Token","in":"header","required":False,"schema":{"type":"string"},"description":"Cookie 会话写入必填，Bearer 请求不需要。"})
                if path.startswith("/api/admin/") and method!="get":
                    operation.setdefault("parameters",[]).append({"name":"Idempotency-Key","in":"header","required":True,"schema":{"type":"string","minLength":8,"maxLength":128},"description":"同一次写操作重试复用，保留7天。凭证秘密只展示一次。"})
        app.openapi_schema=schema
        return schema
    app.openapi=openapi_schema

    @app.get("/api/docs",include_in_schema=False,response_class=HTMLResponse)
    def api_docs():
        return (ROOT/"backend"/"api-docs.html").read_text(encoding="utf-8")

    @app.get("/api/health",tags=["公开"])
    def health():
        with db.connect() as conn:
            conn.execute("SELECT 1")
        return {"status":"ok","service":"haoke-game-hub","version":app.version,"environment":cfg.env,"battle":"host-relay","matchmaking":"native","play_entry":"game","protocol":online.PROTOCOL}

    @app.get("/api/config",tags=["公开"])
    def public_config(request:Request):
        with db.connect() as conn:
            return {"site":setting_values(conn),"environment":cfg.env,"mail_mode":cfg.mail_mode,
                    "public_url":cfg.public_url,"local_preview":cfg.env!="production",
                    "dev_mailbox_available":cfg.env=="development" and cfg.mail_mode=="development" and auth.loopback(request),
                    "admin_hint":cfg.admin_email if cfg.env=="development" and auth.loopback(request) else None,
                    "emotes":allrows(conn,"SELECT * FROM emotes WHERE enabled=1 ORDER BY cell")}

    @app.get("/api/games",tags=["公开"])
    def games():
        with db.connect() as conn:
            result=allrows(conn,"SELECT * FROM games WHERE status='visible' ORDER BY created_at")
            for game in result:
                game["releases"]=allrows(conn,"SELECT * FROM releases WHERE game_id=? ORDER BY created_at DESC",(game["id"],))
        return {"games":result}

    @app.get("/api/games/{game_id}",tags=["公开"])
    def game_detail(game_id:str):
        with db.connect() as conn:
            game=rooms.get_game(conn,game_id)
            game["releases"]=allrows(conn,"SELECT * FROM releases WHERE game_id=? ORDER BY created_at DESC",(game_id,))
        return {"game":game}

    frontend=ROOT/"frontend"/"dist"
    @app.get("/{path:path}",include_in_schema=False)
    def frontend_file(path:str):
        if path.startswith(("api/","ws")):
            return JSONResponse({"error":{"code":"NOT_FOUND","message":"接口不存在"}},status_code=404)
        if not (frontend/"index.html").exists():
            return JSONResponse({"message":"请先在 frontend 运行 npm run build"},status_code=503)
        target=(frontend/path).resolve()
        if frontend.resolve() not in target.parents:
            target=frontend/"index.html"
        if target.is_file():
            return FileResponse(target)
        if Path(path).suffix:
            return JSONResponse({"error":{"code":"ASSET_NOT_FOUND","message":"资源不存在"}},status_code=404)
        return FileResponse(frontend/"index.html",headers={"Cache-Control":"no-cache"})
    return app
