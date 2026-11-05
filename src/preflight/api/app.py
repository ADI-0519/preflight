import asyncio
import json
import logging
import os
import re
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from preflight.api.auth import CODE_SECONDS, COOKIE, PENDING, SESSION_SECONDS, Auth
from preflight.api.contracts import (
    Approval,
    ApprovalView,
    Code,
    FixView,
    JobList,
    JobView,
    Rename,
    SignIn,
    StartFix,
    StartScreening,
    StartUpload,
    UploadView,
)
from preflight.api.public import Public
from preflight.api.service import Service
from preflight.api.storage import OWNER, TERMINAL, APIError, Settings, mine
from preflight.api.web import ROOT, install_web
from preflight.ingest import MAX_SECONDS, probe, run
from preflight.ingest.script import MAX_SCRIPT_BYTES, SCRIPT_TYPES, ScriptError, read_script
from preflight.schema import NOTICE, Screening

log = logging.getLogger(__name__)

MEDIA = {
    **SCRIPT_TYPES,
    "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
    # the Model API reads video only as MP4 or MOV, so WebM is refused at upload
    "video/mp4": ".mp4", "video/quicktime": ".mov",
}
# Cloud Run refuses any request over 32 MiB, so larger files arrive in parts of at most this size
PART_BYTES = 16 * 1024 * 1024
PART_PATH = re.compile(r"^/uploads/[0-9a-f]{32}/parts$")
MEDIA_INPUT_OPTIONS = (
    "-protocol_whitelist", "file,pipe",
    "-format_whitelist", "mov,png_pipe,jpeg_pipe,webp_pipe",
)


def media_kind(media_type: str | None) -> str | None:
    if media_type is None:
        return None
    return "script" if media_type in SCRIPT_TYPES else media_type.split("/")[0]


def validate_media(path, max_seconds: float = MAX_SECONDS):
    options = MEDIA_INPUT_OPTIONS
    if path.suffix == ".jpg":
        # JPEG auto-detection can select image2, which also supports file sequences.
        options += ("-f", "jpeg_pipe")
    info = probe(path, input_options=options)
    if info["duration"] > max_seconds:
        raise APIError(422, "media_too_long")
    # ffprobe can identify a container from its extension even when no frame decodes.
    run("ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", *options, "-i", str(path),
        "-frames:v", "1", "-f", "null", "-")
    return info


class BodyLimit:
    def __init__(self, app, settings: Settings, public: Public):
        self.app, self.settings, self.public = app, settings, public

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"]
        limit = (self.public.max_upload_bytes() if path == "/uploads"
                 else PART_BYTES if PART_PATH.fullmatch(path) else self.settings.max_json_bytes)
        size = 0

        async def limited_receive():
            nonlocal size
            message = await receive()
            size += len(message.get("body", b""))
            if size > limit:
                raise HTTPException(413, "body_too_large")
            return message

        await self.app(scope, limited_receive, send)


def create_app(
    settings: Settings | None = None, *, web_root: Path | None = None,
    demo_root: Path | None = None, results_root: Path | None = None, auth: Auth | None = None, **dependencies,
) -> FastAPI:
    """Single-process app; sign-in is on when FIREBASE_PROJECT_ID is set (preflight.api.auth)."""
    if settings is None:
        cap = os.environ.get("PREFLIGHT_DAILY_CAP_USD", "").strip()
        # public mode's daily model spend cap; a deployment open to anyone sets it below the default
        settings = Settings(daily_cap_usd=float(cap)) if cap else Settings()
    auth = auth or Auth.from_env()
    service = Service(settings, **dependencies)
    storage, public = service.storage, service.public

    async def reap():
        while True:
            await asyncio.sleep(settings.sweep_seconds)
            try:
                await asyncio.to_thread(storage.sweep)
            except Exception as e:
                # rule 6: one bad sweep must not end expiry for the life of the process; the next one retries
                log.warning("retention sweep failed: %s", type(e).__name__)

    @asynccontextmanager
    async def lifespan(app):
        storage.start()
        task = asyncio.create_task(reap())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            await asyncio.to_thread(service.executor.shutdown, wait=True)
            with suppress(OSError):
                storage.sweep()

    app = FastAPI(title="PreFlight API", version="0.1.0", lifespan=lifespan)
    app.state.service = service
    app.state.auth = auth
    app.add_middleware(BodyLimit, settings=settings, public=public)
    # a deployment names its public host names (PREFLIGHT_ALLOWED_HOSTS, comma-separated); local runs need none
    hosts = [h.strip() for h in os.environ.get("PREFLIGHT_ALLOWED_HOSTS", "").split(",") if h.strip()]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver", *hosts])

    @app.middleware("http")
    async def private_errors(request, call_next):
        try:
            response = await call_next(request)
        except Exception:
            return JSONResponse({"error": "internal_error", "notice": NOTICE}, status_code=500,
                                headers={"Cache-Control": "no-store"})
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.middleware("http")
    async def signed_in(request, call_next):
        request.state.user = auth.user(request.cookies.get(COOKIE)) if auth.enabled else None
        if auth.required(request.url.path) and request.state.user is None:
            return JSONResponse({"error": "login_required", "notice": NOTICE}, status_code=401,
                                headers={"Cache-Control": "no-store"})
        # storage checks every upload and job against this account (preflight.api.storage.mine)
        OWNER.set(request.state.user.uid if request.state.user else None)
        return await call_next(request)

    @app.exception_handler(APIError)
    async def api_error(request, error):
        wait = error.detail.get("retry_after")
        return JSONResponse({"error": error.code, **error.detail, "notice": NOTICE}, status_code=error.status,
                            headers={"Retry-After": str(wait)} if wait else None)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        # FastAPI's default errors include raw input values.
        return JSONResponse({"error": "invalid_request", "notice": NOTICE}, status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, error):
        return JSONResponse({"error": "request_rejected", "notice": NOTICE}, status_code=error.status_code)

    def client(request: Request) -> str:
        # a signed-in visitor is limited as one account wherever they connect from
        if user := getattr(request.state, "user", None):
            return f"user:{user.uid}"
        # behind a proxy, run uvicorn with --proxy-headers so this is the visitor's address
        return request.client.host if request.client else "unknown"

    def signed_in_as(request: Request) -> dict:
        user = request.state.user
        pending = None if user or not auth.enabled else auth.user(request.cookies.get(PENDING), stage="code")
        return {"signed_in": user is not None, "email": user.email if user else None, "login": auth.enabled,
                "pending": pending.email if pending else None}

    def set_cookie(response, request: Request, name: str, value: str, seconds: int) -> None:
        response.set_cookie(name, value, max_age=seconds, httponly=True, samesite="lax",
                            secure=request.url.scheme == "https", path="/")

    def waiting(request: Request):
        if not auth.enabled:
            raise APIError(404, "login_not_enabled")
        user = auth.user(request.cookies.get(PENDING), stage="code")
        if user is None:
            raise APIError(401, "code_session_expired")
        return user

    @app.post("/auth/session")
    def sign_in(fields: SignIn, request: Request):
        # a checked Firebase sign-in only earns the wait for the emailed code; the session comes after it
        if not auth.enabled:
            raise APIError(404, "login_not_enabled")
        user = auth.sign_in(fields.id_token)
        auth.send(user)
        response = JSONResponse({"signed_in": False, "email": None, "login": True, "pending": user.email})
        set_cookie(response, request, PENDING, auth.cookie(user, stage="code"), CODE_SECONDS)
        return response

    @app.post("/auth/code")
    def enter_code(fields: Code, request: Request):
        user = waiting(request)
        auth.check(user, fields.code)
        response = JSONResponse({"signed_in": True, "email": user.email, "login": True, "pending": None})
        # replaces the half-signed-in cookie, which has the same name
        set_cookie(response, request, COOKIE, auth.cookie(user), SESSION_SECONDS)
        return response

    @app.post("/auth/code/resend")
    def resend_code(request: Request):
        auth.send(waiting(request), again=True)
        return {"sent": True}

    @app.post("/auth/logout")
    def sign_out():
        response = JSONResponse({"signed_in": False, "email": None, "login": auth.enabled, "pending": None})
        response.delete_cookie(COOKIE, path="/")
        return response

    @app.get("/auth/me")
    def me(request: Request):
        return signed_in_as(request)

    def view(job):
        return {"job_id": job["job_id"], "kind": job["kind"], "status": job["status"], "notice": NOTICE}

    @app.get("/health")
    def health():
        return {"status": "ready", "notice": NOTICE}

    async def check_saved(path: Path, media_type: str, size: int) -> None:
        if not size:
            raise APIError(422, "empty_upload")
        if media_type in SCRIPT_TYPES:
            try:
                await asyncio.to_thread(read_script, path)
            except ScriptError as exc:
                code = str(exc)
                status = 415 if code in {"invalid_script_encoding", "invalid_script_content"} else 422
                raise APIError(status, code) from None
        else:
            try:
                info = await asyncio.to_thread(validate_media, path, public.max_seconds(MAX_SECONDS))
            except (ValueError, RuntimeError):
                raise APIError(415, "unreadable_media") from None
            if info["still"] != media_type.startswith("image/"):
                raise APIError(415, "media_type_mismatch")

    def upload_limit(media_type: str) -> int:
        limit = public.max_upload_bytes()
        return min(limit, MAX_SCRIPT_BYTES) if media_type in SCRIPT_TYPES else limit

    @app.post("/uploads", status_code=201, response_model=UploadView, openapi_extra={
        "requestBody": {"required": True, "content": {
            media_type: {"schema": {"type": "string", "format": "binary"}} for media_type in MEDIA
        }},
    })
    async def upload(request: Request):
        media_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
        if media_type not in MEDIA:
            raise APIError(415, "unsupported_media_type")
        with public.admit(client(request), "upload"):
            limit = upload_limit(media_type)
            fields = storage.begin(media_type, MEDIA[media_type])
            saved, size = False, 0
            try:
                path = storage.upload_dir(fields["upload_id"]) / ("media" + fields["suffix"])
                with path.open("xb") as stream:
                    async for chunk in request.stream():
                        size += len(chunk)
                        if size > limit:
                            raise APIError(413, "body_too_large")
                        stream.write(chunk)
                await check_saved(path, media_type, size)
                fields = storage.finish(fields, size)
                saved = True
                keys = ("upload_id", "media_type", "bytes", "expires_at")
                return {key: fields[key] for key in keys} | {"notice": NOTICE}
            finally:
                if not saved:
                    storage.discard(fields["upload_id"])

    parts_lock: dict[str, asyncio.Lock] = {}

    def unfinished(upload_id: str) -> tuple[dict, Path]:
        directory = storage.upload_dir(upload_id)
        meta = directory / "upload.json"
        if not meta.is_file():
            raise APIError(404, "upload_not_found")
        fields = json.loads(meta.read_text(encoding="utf-8"))
        # another account's unfinished upload reads as missing, as finished ones do in storage.upload()
        if not mine(fields):
            raise APIError(404, "upload_not_found")
        if fields["stored"] or "expected" not in fields:
            raise APIError(409, "upload_already_complete")
        if fields["expires_at"] <= storage.clock():
            raise APIError(410, "upload_expired")
        return fields, directory / ("media" + fields["suffix"])

    @app.post("/uploads/parts", status_code=201)
    def start_parts(fields: StartUpload, request: Request):
        """Starts a file sent in parts. The visitor's upload allowance is used here, once per file."""
        media_type = fields.media_type.lower()
        if media_type not in MEDIA:
            raise APIError(415, "unsupported_media_type")
        if fields.bytes > upload_limit(media_type):
            raise APIError(413, "body_too_large")
        with public.admit(client(request), "upload"):
            started = storage.begin(media_type, MEDIA[media_type])
            started = started | {"expected": fields.bytes}
            with storage.lock:
                storage.write(started)
                # unfinished parts are not pinned: the sweep deletes them at expiry like any upload
                storage.release((started["upload_id"],))
            (storage.upload_dir(started["upload_id"]) / ("media" + started["suffix"])).touch()
            return {"upload_id": started["upload_id"], "part_bytes": PART_BYTES, "notice": NOTICE}

    @app.post("/uploads/{upload_id}/parts")
    async def add_part(upload_id: str, offset: int, request: Request):
        """Appends one part at `offset`; a retried part is refused with the size already received."""
        lock = parts_lock.setdefault(upload_id, asyncio.Lock())
        async with lock:
            fields, path = unfinished(upload_id)
            size = path.stat().st_size
            if offset != size:
                return JSONResponse({"error": "wrong_offset", "received": size, "notice": NOTICE}, status_code=409)
            with path.open("ab") as stream:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > fields["expected"]:
                        stream.truncate(offset)
                        raise APIError(413, "body_too_large")
                    stream.write(chunk)
            return {"received": size, "notice": NOTICE}

    @app.post("/uploads/{upload_id}/complete", status_code=201, response_model=UploadView)
    async def complete_parts(upload_id: str):
        lock = parts_lock.setdefault(upload_id, asyncio.Lock())
        async with lock:
            fields, path = unfinished(upload_id)
            size = path.stat().st_size
            if size != fields["expected"]:
                raise APIError(409, "upload_incomplete")
            try:
                await check_saved(path, fields["media_type"], size)
            except APIError:
                storage.discard(upload_id)
                raise
            finally:
                parts_lock.pop(upload_id, None)
            fields = storage.finish({k: v for k, v in fields.items() if k != "expected"}, size)
            keys = ("upload_id", "media_type", "bytes", "expires_at")
            return {key: fields[key] for key in keys} | {"notice": NOTICE}

    @app.post("/screenings", status_code=202, response_model=JobView)
    def start_screening(fields: StartScreening, request: Request):
        with public.admit(client(request), "screening"):
            return view(service.start_screening(fields.upload_id, fields.align, fields.title))

    @app.get("/ui/allowance")
    def allowance(request: Request):
        return {"allowance": public.allowance(client(request)), "notice": NOTICE}

    @app.get("/jobs", response_model=JobList)
    def jobs():
        return {"jobs": [{"job_id": j["job_id"], "kind": j["kind"], "status": j["status"],
                          "upload_id": j["upload_ids"][0], "media": media_kind(j.get("media_type")),
                          "created_at": j.get("created_at"), "title": j.get("title")}
                         for j in storage.owned_jobs()], "notice": NOTICE}

    @app.post("/jobs/{job_id}/retry", status_code=202, response_model=JobView)
    def retry(job_id: str, request: Request):
        with storage.lock:
            source = storage.job(job_id)
        if source["kind"] != "screening":
            raise APIError(409, "screening_required")
        if source["status"] not in {"failed", "incomplete"}:
            raise APIError(409, "nothing_to_retry")
        # the upload's cache answers every stage that finished, so only the failed ones call a model again
        with public.admit(client(request), "screening"):
            return view(service.start_screening(source["upload_ids"][0], True, source.get("title")))

    @app.patch("/jobs/{job_id}", response_model=JobView)
    def rename(job_id: str, fields: Rename):
        return view(storage.rename(job_id, fields.title))

    @app.get("/jobs/{job_id}", response_model=JobView)
    def job(job_id: str):
        with storage.lock:
            return view(storage.job(job_id))

    @app.get("/screenings/{job_id}", response_model=Screening)
    def screening(job_id: str):
        return service.result(job_id)

    @app.get("/screenings/{job_id}/report", response_class=HTMLResponse)
    def report(job_id: str):
        return Response(service.report(job_id), media_type="text/html", headers={
            "Content-Security-Policy": "default-src 'none'; img-src data:; style-src 'unsafe-inline'; "
                                       "base-uri 'none'; frame-ancestors 'self'",
        })

    @app.get("/jobs/{job_id}/events", response_class=StreamingResponse, responses={
        200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}},
    })
    async def events(job_id: str, request: Request):
        try:
            after = int(request.headers.get("last-event-id", "0"))
            if after < 0:
                raise ValueError
        except ValueError:
            raise APIError(400, "invalid_event_id") from None
        with storage.lock:
            current = storage.job(job_id)
            if after > len(current["events"]):
                raise APIError(400, "invalid_event_id")

        async def stream():
            nonlocal after
            while not await request.is_disconnected():
                try:
                    with storage.lock:
                        current = storage.job(job_id)
                        pending = list(current["events"][after:])
                        terminal = current["status"] in TERMINAL
                except APIError:
                    return
                for event in pending:
                    after = event["id"]
                    yield f'id: {after}\nevent: progress\ndata: {json.dumps(event)}\n\n'
                if terminal:
                    return
                if not pending:
                    yield ": keep-alive\n\n"
                await asyncio.sleep(0.1)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})

    @app.post("/fixes", status_code=202, response_model=JobView)
    def start_fix(fields: StartFix, request: Request):
        with public.admit(client(request), "fix"):
            return view(service.start_fix(fields.screening_id, fields.model_dump()))

    @app.get("/fixes/{job_id}", response_model=FixView)
    def fixing(job_id: str):
        return service.fix_result(job_id) | {"notice": NOTICE}

    @app.post("/fixes/{job_id}/approve", response_model=ApprovalView)
    def approval(job_id: str, fields: Approval, request: Request):
        # with sign-in on, the audit log names the account that approved, not a typed name
        by = request.state.user.email if request.state.user else fields.by
        return {"decision": service.approve(job_id, by, fields.note), "notice": NOTICE}

    @app.get("/fixes/{job_id}/stills/{index}")
    def still(job_id: str, index: int):
        content, media_type = service.still(job_id, index)
        return Response(content, media_type=media_type)

    install_web(app, service, web_root=web_root or ROOT / "web/dist",
                demo_root=demo_root or ROOT / "data/raw/demo", results_root=results_root or ROOT / "results")
    return app
