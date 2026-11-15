import re
from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field, field_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class CodeRequest(StrictModel):
    email: str = Field(min_length=3,max_length=254)
    purpose: Literal["signin","recovery","password"] = "signin"
    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        value = value.lower()
        if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}", value):
            raise ValueError("请输入有效邮箱地址")
        return value

class CodeVerify(StrictModel):
    challenge_id: str = Field(min_length=20,max_length=100)
    code: str = Field(pattern=r"^\d{6}$")
    client: Literal["web","native"] = "web"

class ProfileUpdate(StrictModel):
    nickname: str = Field(min_length=1,max_length=20)
    avatar: int = Field(ge=0,le=15)
    @field_validator("nickname")
    @classmethod
    def plain_nickname(cls, v):
        if any(ord(c)<32 for c in v) or "://" in v:
            raise ValueError("昵称不能含链接或控制字符")
        return v

class GameEntry(StrictModel):
    game_id: str = Field(min_length=1,max_length=64,pattern=r"^[a-z0-9-]+$")

class ReadyUpdate(StrictModel):
    ready: bool

class EmoteSend(StrictModel):
    emote_id: str = Field(min_length=1,max_length=30)

class MuteUpdate(StrictModel):
    muted: bool

class GameWrite(StrictModel):
    id: str = Field(min_length=2,max_length=48,pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(min_length=1,max_length=60)
    tagline: str = Field(min_length=1,max_length=100)
    description: str = Field(min_length=1,max_length=2000)
    genre: str = Field(min_length=1,max_length=60)
    status: Literal["visible","hidden"] = "visible"
    max_players: int = Field(default=6,ge=2,le=6)
    min_players: int = Field(default=2,ge=1,le=6)

class ReleaseWrite(StrictModel):
    platform: Literal["android","ios","windows","macos"]
    version: str = Field(min_length=1,max_length=40)
    url: str = Field(min_length=8,max_length=2048)
    notes: str = Field(default="",max_length=2000)
    @field_validator("url")
    @classmethod
    def safe_url(cls,value):
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("下载地址必须为不含凭证的 HTTPS 链接")
        return value

class SettingsWrite(StrictModel):
    site_name: str = Field(min_length=1,max_length=40)
    tagline: str = Field(min_length=1,max_length=100)
    announcement: str = Field(max_length=1000)
    qq_group: str = Field(pattern=r"^\d{5,12}$")

class UserAdminWrite(StrictModel):
    nickname: str = Field(min_length=1,max_length=20)
    role: Literal["user","admin"]
    status: Literal["active","suspended"]

class KeyCreate(StrictModel):
    name: str = Field(min_length=1,max_length=60)
    scope: Literal["admin:full","admin:read"]
    expires_days: int = Field(default=30,ge=1,le=365)

class EmoteAdminWrite(StrictModel):
    label: str = Field(min_length=1,max_length=20)
    enabled: bool

class GameProfileWrite(StrictModel):
    nickname: str = Field(min_length=1,max_length=20)
    data: dict = Field(default_factory=dict)
