from contextlib import contextmanager
import json
import sqlite3
import time

EMOTES = [
    ("hello", "你好"), ("ready", "准备好了"), ("roger", "收到"), ("rally", "集合"),
    ("help", "我来帮忙"), ("careful", "小心"), ("retreat", "撤退"), ("wait", "等一下"),
    ("great", "干得漂亮"), ("thanks", "谢谢"), ("sorry", "抱歉"), ("phew", "好险"),
    ("haha", "哈哈"), ("wow", "震惊"), ("gg", "打得好"), ("again", "再来一局"),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS migrations(version INTEGER PRIMARY KEY, applied_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,nickname TEXT NOT NULL,avatar INTEGER NOT NULL DEFAULT 0,role TEXT NOT NULL DEFAULT 'user',status TEXT NOT NULL DEFAULT 'active',created_at REAL NOT NULL,last_login REAL NOT NULL);
CREATE TABLE IF NOT EXISTS challenges(id TEXT PRIMARY KEY,email TEXT NOT NULL,digest TEXT NOT NULL,purpose TEXT NOT NULL,created_at REAL NOT NULL,expires_at REAL NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,consumed INTEGER NOT NULL DEFAULT 0,ip TEXT NOT NULL,dev_code TEXT);
CREATE INDEX IF NOT EXISTS challenges_email_time ON challenges(email,created_at);
CREATE INDEX IF NOT EXISTS challenges_ip_time ON challenges(ip,created_at);
CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),csrf TEXT NOT NULL,kind TEXT NOT NULL,created_at REAL NOT NULL,expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS games(id TEXT PRIMARY KEY,slug TEXT UNIQUE NOT NULL,title TEXT NOT NULL,tagline TEXT NOT NULL,description TEXT NOT NULL,genre TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'visible',max_players INTEGER NOT NULL DEFAULT 6,min_players INTEGER NOT NULL DEFAULT 2,integration TEXT NOT NULL DEFAULT 'pending',created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS releases(id TEXT PRIMARY KEY,game_id TEXT NOT NULL REFERENCES games(id),platform TEXT NOT NULL,version TEXT NOT NULL,url TEXT NOT NULL,notes TEXT NOT NULL DEFAULT '',created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS profiles(user_id TEXT NOT NULL REFERENCES users(id),game_id TEXT NOT NULL REFERENCES games(id),nickname TEXT NOT NULL,data TEXT NOT NULL DEFAULT '{}',first_entered REAL NOT NULL,last_entered REAL NOT NULL,PRIMARY KEY(user_id,game_id));
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT NOT NULL,game_id TEXT,kind TEXT NOT NULL,created_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS events_date_kind ON events(created_at,kind,game_id,user_id);
CREATE TABLE IF NOT EXISTS rooms(id TEXT PRIMARY KEY,code TEXT UNIQUE NOT NULL,game_id TEXT NOT NULL REFERENCES games(id),host_id TEXT NOT NULL REFERENCES users(id),status TEXT NOT NULL DEFAULT 'waiting',created_at REAL NOT NULL,updated_at REAL NOT NULL,expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS members(room_id TEXT NOT NULL REFERENCES rooms(id),user_id TEXT NOT NULL REFERENCES users(id),game_id TEXT NOT NULL,ready INTEGER NOT NULL DEFAULT 0,joined_at REAL NOT NULL,last_seen REAL NOT NULL,PRIMARY KEY(room_id,user_id),UNIQUE(game_id,user_id));
CREATE TABLE IF NOT EXISTS emotes(id TEXT PRIMARY KEY,label TEXT NOT NULL,cell INTEGER NOT NULL,enabled INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT,room_id TEXT NOT NULL REFERENCES rooms(id),user_id TEXT NOT NULL REFERENCES users(id),emote_id TEXT NOT NULL REFERENCES emotes(id),created_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS messages_room ON messages(room_id,id);
CREATE TABLE IF NOT EXISTS mutes(user_id TEXT NOT NULL REFERENCES users(id),target_id TEXT NOT NULL REFERENCES users(id),PRIMARY KEY(user_id,target_id));
CREATE TABLE IF NOT EXISTS api_keys(id TEXT PRIMARY KEY,name TEXT NOT NULL,token_hash TEXT UNIQUE NOT NULL,prefix TEXT NOT NULL,scope TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at REAL NOT NULL,expires_at REAL NOT NULL,revoked_at REAL,last_used REAL);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,actor TEXT NOT NULL,action TEXT NOT NULL,target TEXT NOT NULL,before_json TEXT,after_json TEXT,created_at REAL NOT NULL,request_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS idempotency(actor TEXT NOT NULL,key TEXT NOT NULL,signature TEXT NOT NULL,response TEXT NOT NULL,created_at REAL NOT NULL,PRIMARY KEY(actor,key));
CREATE TABLE IF NOT EXISTS ws_tickets(hash TEXT PRIMARY KEY,session_hash TEXT NOT NULL,user_id TEXT NOT NULL,expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS api_requests(id INTEGER PRIMARY KEY AUTOINCREMENT,actor TEXT NOT NULL,method TEXT NOT NULL,path TEXT NOT NULL,status INTEGER NOT NULL,created_at REAL NOT NULL,request_id TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS messages_user_time ON messages(user_id,created_at);
CREATE INDEX IF NOT EXISTS profiles_game_time ON profiles(game_id,first_entered);
CREATE INDEX IF NOT EXISTS members_user ON members(user_id);
CREATE INDEX IF NOT EXISTS api_requests_time ON api_requests(created_at);
"""

class Database:
    def __init__(self, path):
        self.path = str(path)

    @contextmanager
    def connect(self, write=False):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        try:
            if write:
                conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self):
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)
            conn.execute("INSERT OR IGNORE INTO migrations VALUES(1,?)", (time.time(),))
            defaults = {
                "site_name": "浩科游戏中心",
                "tagline": "一个账号，更多好玩的世界。",
                "announcement": "一个账号，连接不同游戏。网站负责发现与分享，组队和匹配将在游戏内完成；Liquid Wars 联网接入准备中。",
                "qq_group": "1136036532",
            }
            for key, value in defaults.items():
                conn.execute("INSERT OR IGNORE INTO settings VALUES(?,?)", (key, json.dumps(value, ensure_ascii=False)))
            conn.execute("""INSERT OR IGNORE INTO games VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                ("liquid-wars", "liquid-wars", "液态战争", "让每一滴，都成为你的力量。",
                 "指挥流动的液体军团，在包围与突围之间寻找胜机。保留大量粒子混战的乐趣，让路线、分兵与据点争夺带来更多选择。",
                 "即时战略 · 液体模拟", "visible", 6, 2, "pending", time.time()))
            for index, (key, label) in enumerate(EMOTES):
                conn.execute("INSERT OR IGNORE INTO emotes VALUES(?,?,?,1)", (key, label, index))
            # Only replace our previous default; preserve any owner's edited announcement.
            if not conn.execute("SELECT 1 FROM migrations WHERE version=2").fetchone():
                old = json.dumps("欢迎来到浩科。Liquid Wars 房间现已开放本地体验，真实对战接入准备中。", ensure_ascii=False)
                conn.execute("UPDATE settings SET value=? WHERE key='announcement' AND value=?",
                             (json.dumps(defaults["announcement"], ensure_ascii=False), old))
                conn.execute("INSERT INTO migrations VALUES(2,?)", (time.time(),))

def rowdict(row):
    return dict(row) if row is not None else None

def allrows(conn, sql, args=()):
    return [dict(row) for row in conn.execute(sql, args).fetchall()]

def setting_values(conn):
    return {row["key"]: json.loads(row["value"]) for row in conn.execute("SELECT * FROM settings")}
