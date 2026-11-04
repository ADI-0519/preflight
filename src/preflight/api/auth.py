"""Sign-in with Firebase Authentication, held as a signed session cookie.

Login is on when FIREBASE_PROJECT_ID is set; otherwise the workspace runs open, as it does locally. The browser
signs in with Firebase (Google or email and password) and trades its ID token for a session cookie, because image,
video and progress-stream requests cannot carry a token header. The server checks the token against Google's
published keys, so it needs no Firebase service account.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import jwt
from dotenv import load_dotenv

from preflight.api.storage import APIError

log = logging.getLogger(__name__)

COOKIE = "preflight_session"
SESSION_SECONDS = 12 * 3600
JWKS_URL = "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"
# open without a session: the page and its assets, its configuration, health and the sign-in routes themselves
OPEN = ("/health", "/ui/config", "/auth/", "/assets/", "/docs", "/openapi.json")


@dataclass(frozen=True)
class User:
    uid: str
    email: str


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
        return cls(
            project_id=env("FIREBASE_PROJECT_ID", "").strip(), api_key=env("FIREBASE_API_KEY", "").strip(),
            auth_domain=env("FIREBASE_AUTH_DOMAIN", "").strip(), app_id=env("FIREBASE_APP_ID", "").strip(),
            allowed=_allowed(env("PREFLIGHT_ALLOWED_EMAILS", "")),
            secret=env("PREFLIGHT_SESSION_SECRET", "").encode(),
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
            # an unverified email could be anyone's, so an allowlist only admits verified addresses
            if not claims.get("email_verified"):
                raise APIError(403, "email_not_verified")
            domain = "@" + email.rpartition("@")[2]
            if email not in self.allowed and domain not in self.allowed:
                raise APIError(403, "not_allowed")
        return User(claims["sub"], email)

    def _mac(self, body: bytes) -> str:
        return base64.urlsafe_b64encode(hmac.new(self.secret, body, hashlib.sha256).digest()).decode().rstrip("=")

    def cookie(self, user: User) -> str:
        body = base64.urlsafe_b64encode(json.dumps(
            {"uid": user.uid, "email": user.email, "exp": int(self.clock()) + SESSION_SECONDS}
        ).encode()).decode().rstrip("=")
        return f"{body}.{self._mac(body.encode())}"

    def user(self, cookie: str | None) -> User | None:
        if not cookie or "." not in cookie:
            return None
        body, mac = cookie.rsplit(".", 1)
        if not hmac.compare_digest(mac, self._mac(body.encode())):
            return None
        try:
            fields = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        except ValueError:
            return None
        if fields.get("exp", 0) <= self.clock():
            return None
        return User(fields["uid"], fields["email"])

    def required(self, path: str) -> bool:
        return self.enabled and path != "/" and not path.startswith(OPEN)

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
