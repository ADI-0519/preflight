import json
from contextlib import nullcontext

import jwt
import pytest
import yaml

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402
from test_api import AGENT, MEDIA, NoPrecedents, recorded_screener, replay_ingest, start, upload, wait_for  # noqa: E402
from test_api import replay_models as replay_models  # noqa: E402, F401  (the fixture)

from preflight.api import Settings, create_app  # noqa: E402
from preflight.api import auth as auth_module  # noqa: E402
from preflight.api.auth import COOKIE, PENDING, Auth, User  # noqa: E402
from preflight.api.storage import APIError  # noqa: E402

PROJECT = "preflight-test"
TOKENS = {
    "founder": {"sub": "u1", "email": "Founder@Example.com", "email_verified": True},
    "unverified": {"sub": "u2", "email": "founder@example.com", "email_verified": False},
    "stranger": {"sub": "u3", "email": "someone@elsewhere.org", "email_verified": True},
}


def verify(token: str) -> dict:
    if token not in TOKENS:
        raise jwt.InvalidTokenError("unknown token")
    return TOKENS[token]


def auth(allowed=(), now=1_000_000.0, clock=None, mail=True):
    outbox = []
    a = Auth(project_id=PROJECT, api_key="key", auth_domain=f"{PROJECT}.firebaseapp.com", app_id="app",
             allowed=allowed, secret=b"s" * 32, clock=clock or (lambda: now), verify=verify,
             send_code=(lambda to, code: outbox.append((to, code))) if mail else None)
    a.outbox = outbox
    return a


@pytest.fixture
def signed(tmp_path, replay_models):
    return create_app(
        Settings(root=tmp_path / "uploads"), auth=auth(),
        models_factory=lambda directory: nullcontext(replay_models),
        precedents_factory=NoPrecedents, ingester=replay_ingest, draft_screener=recorded_screener,
    )


def sign_in(client, token="founder"):
    response = client.post("/auth/session", json={"id_token": token})
    assert response.status_code == 200, response.text
    _, code = client.app.state.auth.outbox[-1]
    response = client.post("/auth/code", json={"code": code})
    assert response.status_code == 200, response.text
    return response


def test_login_is_off_without_a_firebase_project(tmp_path):
    with TestClient(create_app(Settings(root=tmp_path / "uploads"))) as client:
        assert client.get("/ui/config").json()["auth"] is None
        assert client.get("/auth/me").json() == {"signed_in": False, "email": None, "login": False, "pending": None}
        assert client.get("/jobs/" + "0" * 32).status_code == 404
        assert client.post("/auth/session", json={"id_token": "founder"}).status_code == 404


def test_api_routes_need_a_session_but_the_page_and_its_config_do_not(signed):
    with TestClient(signed) as client:
        config = client.get("/ui/config").json()["auth"]
        assert config == {"apiKey": "key", "authDomain": f"{PROJECT}.firebaseapp.com", "projectId": PROJECT,
                          "appId": "app"}
        for path in ("/jobs/" + "0" * 32, "/ui/demos", "/uploads/" + "0" * 32 + "/media"):
            response = client.get(path)
            assert response.status_code == 401 and response.json()["error"] == "login_required"
        assert client.post("/uploads", content=b"x", headers={"Content-Type": "image/png"}).status_code == 401
        assert client.get("/health").status_code == 200
        assert client.get("/auth/me").json()["signed_in"] is False
        for page in ("/", "/login", "/signup"):
            assert client.get(page).status_code != 401


def test_signing_in_sets_a_session_that_lets_the_workspace_run(signed):
    with TestClient(signed) as client:
        response = sign_in(client)
        assert response.json() == {"signed_in": True, "email": "founder@example.com", "login": True, "pending": None}
        cookie = response.headers["set-cookie"]
        assert "httponly" in cookie.lower() and "samesite=lax" in cookie.lower()
        assert client.get("/auth/me").json()["email"] == "founder@example.com"
        job_id = start(client, upload(client, (MEDIA / "captions.mp4").read_bytes(), "video/mp4"))
        assert wait_for(client, job_id) == "completed"
        client.post("/auth/logout")
        assert client.get(f"/jobs/{job_id}").status_code == 401


def test_a_bad_token_or_a_tampered_cookie_is_refused(signed):
    with TestClient(signed) as client:
        response = client.post("/auth/session", json={"id_token": "forged"})
        assert response.status_code == 401 and response.json()["error"] == "invalid_sign_in"
        value = sign_in(client).cookies[COOKIE]
        body, mac = value.rsplit(".", 1)
        client.cookies.clear()
        client.cookies.set(COOKIE, body + "." + mac[::-1])
        assert client.get("/ui/demos").status_code == 401


def test_a_session_expires():
    a, later = auth(), auth(now=1_000_000.0 + 13 * 3600)
    cookie = a.cookie(User("u1", "founder@example.com"))
    assert a.user(cookie) == User("u1", "founder@example.com")
    assert later.user(cookie) is None


def test_the_allowlist_admits_named_and_domain_accounts():
    a = auth(allowed=("founder@example.com",))
    assert a.sign_in("founder").email == "founder@example.com"
    # the emailed code proves the address, so Firebase's own verification flag is not needed
    assert a.sign_in("unverified").email == "founder@example.com"
    with pytest.raises(APIError) as refused:
        a.sign_in("stranger")
    assert refused.value.code == "not_allowed"
    assert auth(allowed=("@elsewhere.org",)).sign_in("stranger").email == "someone@elsewhere.org"
    assert auth().sign_in("unverified").uid == "u2"


def test_the_page_policy_lets_the_google_sign_in_run_only_when_login_is_on():
    on, off = auth().page_policy(), Auth().page_policy()
    assert "https://apis.google.com" in on and f"https://{PROJECT}.firebaseapp.com" in on
    assert "identitytoolkit.googleapis.com" in on
    assert "google" not in off and "script-src 'self';" in off


def test_an_approval_names_the_signed_in_account(signed):
    with TestClient(signed) as client:
        sign_in(client)
        still = upload(client)
        source = start(client, upload(client, (MEDIA / "captions.mp4").read_bytes(), "video/mp4"))
        assert wait_for(client, source) == "completed"
        draft = yaml.safe_load((AGENT / "draft.yaml").read_text(encoding="utf-8"))
        draft["scenes"][0].pop("still")
        draft["scenes"][0]["upload_id"] = still
        job_id = client.post("/fixes", json={"screening_id": source, **draft}).json()["job_id"]
        assert wait_for(client, job_id) == "completed"
        response = client.post(f"/fixes/{job_id}/approve", json={"by": "Someone Else"})
        assert response.status_code == 200, response.text
        directory = signed.state.service.storage.job_dir(signed.state.service.storage.jobs[job_id])
        record = json.loads((directory / "audit.jsonl").read_text(encoding="utf-8").splitlines()[-1])
        assert record["by"] == "founder@example.com"


def test_a_sign_in_waits_for_the_emailed_code(signed):
    with TestClient(signed) as client:
        response = client.post("/auth/session", json={"id_token": "founder"})
        assert response.json() == {"signed_in": False, "email": None, "login": True, "pending": "founder@example.com"}
        assert client.get("/ui/demos").status_code == 401
        assert client.get("/auth/me").json()["pending"] == "founder@example.com"
        # the half-signed-in cookie, under the session's name, is not a session
        assert signed.state.auth.user(client.cookies[COOKIE]) is None
        to, code = signed.state.auth.outbox[-1]
        assert to == "founder@example.com" and len(code) == 6 and code.isdigit()
        wrong = f"{(int(code) + 1) % 10**6:06d}"
        assert client.post("/auth/code", json={"code": wrong}).json()["error"] == "wrong_code"
        assert client.post("/auth/code", json={"code": "12ab56"}).status_code == 422
        assert client.post("/auth/code", json={"code": code}).json()["signed_in"] is True
        assert client.get("/ui/demos").status_code == 200
        # the session replaced the half-signed-in cookie under the one name Firebase Hosting passes through
        assert COOKIE == PENDING == "__session"
        assert signed.state.auth.user(client.cookies[COOKIE]) is not None
        # a code works once
        client.cookies.clear()
        client.cookies.set(PENDING, signed.state.auth.cookie(User("u1", "founder@example.com"), "code"))
        assert client.post("/auth/code", json={"code": code}).json()["error"] == "code_expired"


def test_codes_expire_lock_after_five_wrong_tries_and_resend_once_a_minute():
    now = [1_000_000.0]
    a = auth(clock=lambda: now[0])
    user = User("u1", "founder@example.com")
    a.send(user)
    code = a.outbox[-1][1]
    a.send(user)  # signing in again within a minute keeps the same code
    assert len(a.outbox) == 1
    with pytest.raises(APIError) as early:
        a.send(user, again=True)
    assert early.value.code == "code_recently_sent"
    wrong = f"{(int(code) + 1) % 10**6:06d}"
    for attempt in range(5):
        with pytest.raises(APIError) as refused:
            a.check(user, wrong)
        assert refused.value.code == ("too_many_attempts" if attempt == 4 else "wrong_code")
    with pytest.raises(APIError) as locked:
        a.check(user, code)
    assert locked.value.code == "code_expired"
    now[0] += 61
    a.send(user, again=True)
    now[0] += 10 * 60
    with pytest.raises(APIError) as late:
        a.check(user, a.outbox[-1][1])
    assert late.value.code == "code_expired"


def test_sign_in_is_refused_when_no_mail_is_set_up(tmp_path):
    app = create_app(Settings(root=tmp_path / "uploads"), auth=auth(mail=False))
    with TestClient(app) as client:
        response = client.post("/auth/session", json={"id_token": "founder"})
        assert response.status_code == 503 and response.json()["error"] == "email_codes_not_configured"
        assert PENDING not in client.cookies


def test_the_code_email_goes_over_tls(monkeypatch):
    sent = []

    class Server:
        def __init__(self, host, port, timeout):
            sent.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            sent.append(("starttls",))

        def login(self, user, password):
            sent.append(("login", user))

        def send_message(self, message):
            sent.append(("send", message["To"], message["Subject"], message.get_content()))

    monkeypatch.setattr(auth_module.smtplib, "SMTP", Server)
    auth_module.smtp_sender("smtp.example.com", 587, "bot@example.com", "pw", "bot@example.com")(
        "founder@example.com", "123456")
    assert sent[:3] == [("connect", "smtp.example.com", 587), ("starttls",), ("login", "bot@example.com")]
    assert sent[3][1:3] == ("founder@example.com", "123456 is your PreFlight code")
    assert "expires in 10 minutes" in sent[3][3]
