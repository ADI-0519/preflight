"""Sign-in with Firebase Authentication, held as a signed session cookie.

Login is on when FIREBASE_PROJECT_ID is set; otherwise the workspace runs open, as it does locally. The browser
signs in with Firebase (Google or email and password) and trades its ID token for a session cookie, because image,
video and progress-stream requests cannot carry a token header. The server checks the token against Google's
published keys, so it needs no Firebase service account.

Every sign-in, Google or email, then waits for a six-digit code sent to the account's email, so the workspace knows
the person can read that inbox. The code is mailed over SMTP (PREFLIGHT_SMTP_*); for local work,
PREFLIGHT_DEV_CODES=1 writes it to the server log instead.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import smtplib
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from email.message import EmailMessage

import jwt
from dotenv import load_dotenv

from preflight.api.storage import APIError

log = logging.getLogger(__name__)

# Firebase Hosting passes only a cookie named __session to Cloud Run, so the session and the half-signed-in
# state share it; the signed stage inside tells them apart (Auth.user)
COOKIE = "__session"
SESSION_SECONDS = 12 * 3600
# the half-signed-in state between a Firebase sign-in and the emailed code
PENDING = COOKIE
CODE_SECONDS = 10 * 60
CODE_ATTEMPTS = 5
RESEND_SECONDS = 60
JWKS_URL = "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"
# open without a session: the page and its assets, its configuration, health and the sign-in routes themselves
PAGES = ("/", "/login", "/signup")  # each serves the page, which shows the sign-in screen itself
OPEN = ("/health", "/ui/config", "/auth/", "/assets/", "/docs", "/openapi.json")


@dataclass(frozen=True)
class User:
    uid: str
    email: str


@dataclass
class _Code:
    digest: str
    expires: float
    sent: float
    attempts: int = 0


def smtp_sender(host: str, port: int, user: str, password: str, sender: str) -> Callable[[str, str], None]:
    def send(to: str, code: str) -> None:
        message = EmailMessage()
        message["From"], message["To"] = sender, to
        message["Subject"] = f"{code} is your PreFlight code"
        message.set_content(
            f"Your PreFlight sign-in code is {code}.\n\n"
            f"It expires in {CODE_SECONDS // 60} minutes. If you did not try to sign in, ignore this email; "
            "nobody can get in without the code.\n"
        )
        smtp = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
        with smtp(host, port, timeout=15) as server:
            if port != 465:
                server.starttls()
            if user:
                server.login(user, password)
            server.send_message(message)
    return send


def _log_code(to: str, code: str) -> None:
    log.warning("PREFLIGHT_DEV_CODES is on: sign-in code for %s is %s (local use only)", to, code)


def _allowed(entries: str) -> tuple[str, ...]:
    return tuple(e.strip().lower() for e in entries.split(",") if e.strip())


@dataclass
class Auth:
    project_id: str = ""
    api_key: str = ""
    auth_domain: str = ""
    app_id: str = ""
    # comma-separated emails, or @domain for a whole domain; empty lets any signed-in account in
    allowed: tuple[str, ...] = ()
    secret: bytes = field(default=b"", repr=False)
    clock: Callable[[], float] = time.time
    verify: Callable[[str], dict] | None = field(default=None, repr=False)
    # mails a sign-in code; None refuses sign-in with email_codes_not_configured
    send_code: Callable[[str, str], None] | None = field(default=None, repr=False)
    _codes: dict[str, _Code] = field(default_factory=dict, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self):
        if self.enabled and not self.secret:
            # sessions then last only as long as the process; set PREFLIGHT_SESSION_SECRET to keep them over restarts
            log.warning("PREFLIGHT_SESSION_SECRET is not set; signing sessions with a key for this process only")
            self.secret = secrets.token_bytes(32)
        if self.verify is None:
            keys = jwt.PyJWKClient(JWKS_URL, cache_keys=True)
            self.verify = lambda token: self._firebase_claims(token, keys)

    @classmethod
    def from_env(cls) -> "Auth":
        load_dotenv()
        env = os.environ.get
        send = None
        if host := env("PREFLIGHT_SMTP_HOST", "").strip():
            user = env("PREFLIGHT_SMTP_USER", "").strip()
            send = smtp_sender(host, int(env("PREFLIGHT_SMTP_PORT", "587")), user, env("PREFLIGHT_SMTP_PASSWORD", ""),
                               env("PREFLIGHT_MAIL_FROM", "").strip() or user)
        elif env("PREFLIGHT_DEV_CODES", "").strip() == "1":
            send = _log_code
        return cls(
            project_id=env("FIREBASE_PROJECT_ID", "").strip(), api_key=env("FIREBASE_API_KEY", "").strip(),
            auth_domain=env("FIREBASE_AUTH_DOMAIN", "").strip(), app_id=env("FIREBASE_APP_ID", "").strip(),
            allowed=_allowed(env("PREFLIGHT_ALLOWED_EMAILS", "")),
            secret=env("PREFLIGHT_SESSION_SECRET", "").encode(), send_code=send,
        )

    @property
    def enabled(self) -> bool:
        return bool(self.project_id)

    def client_config(self) -> dict | None:
        # these identify the Firebase project to the browser; Firebase treats them as public
        if not self.enabled:
            return None
        return {"apiKey": self.api_key, "authDomain": self.auth_domain, "projectId": self.project_id,
                "appId": self.app_id}

    def _firebase_claims(self, token: str, keys: jwt.PyJWKClient) -> dict:
        key = keys.get_signing_key_from_jwt(token).key
        return jwt.decode(token, key, algorithms=["RS256"], audience=self.project_id,
                          issuer=f"https://securetoken.google.com/{self.project_id}",
                          options={"require": ["exp", "iat", "sub"]})

    def sign_in(self, id_token: str) -> User:
        try:
            claims = self.verify(id_token)
        except (jwt.PyJWTError, ValueError):
            raise APIError(401, "invalid_sign_in") from None
        email = str(claims.get("email", "")).lower()
        if not claims.get("sub") or not email:
            raise APIError(401, "invalid_sign_in")
        if self.allowed:
            # the emailed code proves the address before any session starts, so an allowlist can trust it
            domain = "@" + email.rpartition("@")[2]
            if email not in self.allowed and domain not in self.allowed:
                raise APIError(403, "not_allowed")
        return User(claims["sub"], email)

    def _mac(self, body: bytes) -> str:
        return base64.urlsafe_b64encode(hmac.new(self.secret, body, hashlib.sha256).digest()).decode().rstrip("=")

    def cookie(self, user: User, stage: str = "session") -> str:
        seconds = SESSION_SECONDS if stage == "session" else CODE_SECONDS
        body = base64.urlsafe_b64encode(json.dumps(
            {"uid": user.uid, "email": user.email, "exp": int(self.clock()) + seconds, "stage": stage}
        ).encode()).decode().rstrip("=")
        return f"{body}.{self._mac(body.encode())}"

    def send(self, user: User, again: bool = False) -> None:
        """Emails a fresh code; a second sign-in within a minute keeps the code already sent."""
        if self.send_code is None:
            raise APIError(503, "email_codes_not_configured")
        now = self.clock()
        with self._lock:
            current = self._codes.get(user.uid)
            if current and now - current.sent < RESEND_SECONDS and current.expires > now:
                if again:
                    raise APIError(429, "code_recently_sent")
                return
            code = f"{secrets.randbelow(10**6):06d}"
            self._codes[user.uid] = _Code(self._mac(f"{user.uid}:{code}".encode()), now + CODE_SECONDS, now)
        try:
            self.send_code(user.email, code)
        except (OSError, smtplib.SMTPException):
            log.exception("sending the sign-in code failed")
            with self._lock:
                self._codes.pop(user.uid, None)
            raise APIError(502, "code_not_sent") from None

    def check(self, user: User, code: str) -> None:
        with self._lock:
            current = self._codes.get(user.uid)
            if current is None or current.expires <= self.clock():
                self._codes.pop(user.uid, None)
                raise APIError(400, "code_expired")
            if not hmac.compare_digest(current.digest, self._mac(f"{user.uid}:{code}".encode())):
                current.attempts += 1
                if current.attempts >= CODE_ATTEMPTS:
                    del self._codes[user.uid]
                    raise APIError(429, "too_many_attempts")
                raise APIError(400, "wrong_code")
            del self._codes[user.uid]

    def user(self, cookie: str | None, stage: str = "session") -> User | None:
        if not cookie or "." not in cookie:
            return None
        body, mac = cookie.rsplit(".", 1)
        if not hmac.compare_digest(mac, self._mac(body.encode())):
            return None
        try:
            fields = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        except ValueError:
            return None
        if fields.get("exp", 0) <= self.clock() or fields.get("stage") != stage:
            return None
        return User(fields["uid"], fields["email"])

    def required(self, path: str) -> bool:
        return self.enabled and path not in PAGES and not path.startswith(OPEN)

    def page_policy(self) -> str:
        # the sign-in popup loads Google's script, frames the project's auth domain and calls Google's token APIs
        google = ""
        if self.enabled:
            frame = f"https://{self.auth_domain}" if self.auth_domain else "https://*.firebaseapp.com"
            google = (" https://apis.google.com", f" {frame} https://accounts.google.com",
                      " https://identitytoolkit.googleapis.com https://securetoken.googleapis.com"
                      " https://www.googleapis.com")
        script, frames, connect = google or ("", "", "")
        return (f"default-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; style-src 'self'; "
                f"script-src 'self'{script}; connect-src 'self'{connect}; frame-src 'self'{frames}; "
                "base-uri 'none'; frame-ancestors 'none'")
