from dataclasses import dataclass, field
import os
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parent.parent

def load_env():
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"'))

@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: ROOT / "data")
    env: str = "development"
    public_url: str = "http://127.0.0.1:8768"
    admin_email: str = "owner@haoke.local"
    secret: str = ""
    mail_mode: str = "development"
    allowed_hosts: list = field(default_factory=lambda: ["127.0.0.1", "localhost", "testserver"])
    allowed_origins: list = field(default_factory=lambda: ["http://127.0.0.1:8768", "http://localhost:8768", "http://127.0.0.1:5178", "http://testserver"])
    otp_cooldown: int = 60
    emote_cooldown: float = 3
    reconnect_grace: int = 90
    session_seconds: int = 7 * 86400
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_security: str = "starttls"

    def prepare(self):
        if self.env not in ("development","production") or self.mail_mode not in ("development","smtp"):
            raise RuntimeError("APP_ENV / MAIL_MODE contains an unsupported value.")
        if self.smtp_security not in ("starttls","ssl"):
            raise RuntimeError("SMTP_SECURITY must be starttls or ssl.")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.secret:
            if self.env == "production":
                raise RuntimeError("Production requires an explicit APP_SECRET.")
            secret_file = self.data_dir / ".app-secret"
            if secret_file.exists():
                self.secret = secret_file.read_text().strip()
            else:
                self.secret = secrets.token_urlsafe(48)
                secret_file.write_text(self.secret)
        if self.env == "production":
            if self.mail_mode != "smtp" or not self.smtp_host or not self.smtp_from:
                raise RuntimeError("Production requires real SMTP configuration.")
            if not self.public_url.startswith("https://") or len(self.secret) < 32:
                raise RuntimeError("Production requires HTTPS and a strong APP_SECRET.")
            if not self.admin_email or self.admin_email.endswith(".local"):
                raise RuntimeError("Set ADMIN_EMAIL to the owner's real email before deployment.")
            if "*" in self.allowed_hosts or "*" in self.allowed_origins:
                raise RuntimeError("Production does not allow wildcard hosts/origins.")

def from_env():
    load_env()
    return Settings(
        data_dir=Path(os.environ.get("DATA_DIR", str(ROOT / "data"))),
        env=os.environ.get("APP_ENV", "development"),
        public_url=os.environ.get("PUBLIC_URL", "http://127.0.0.1:8768").rstrip("/"),
        admin_email=os.environ.get("ADMIN_EMAIL", "owner@haoke.local").strip().lower(),
        secret=os.environ.get("APP_SECRET", ""),
        mail_mode=os.environ.get("MAIL_MODE", "development"),
        allowed_hosts=os.environ.get("ALLOWED_HOSTS", "127.0.0.1,localhost").split(","),
        allowed_origins=os.environ.get("ALLOWED_ORIGINS", "http://127.0.0.1:8768,http://localhost:8768,http://127.0.0.1:5178").split(","),
        smtp_host=os.environ.get("SMTP_HOST", ""), smtp_port=int(os.environ.get("SMTP_PORT", "587")),
        smtp_user=os.environ.get("SMTP_USER", ""), smtp_password=os.environ.get("SMTP_PASSWORD", ""),
        smtp_from=os.environ.get("SMTP_FROM", ""), smtp_security=os.environ.get("SMTP_SECURITY", "starttls"),
    )
