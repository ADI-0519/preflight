# Screening API

The API is a FastAPI service over the same pipeline as the command line. It accepts an upload, runs a screening or a fix as a background job, streams the job's progress, and records a person's approval of a fixed draft. It flags possible issues and explains them; whether an ad runs is a person's decision. The web workspace ([web.md](web.md)) is a client of this API.

## Run

```powershell
uv sync --locked --extra api --extra page
uv run --extra api uvicorn preflight.api:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

The typed OpenAPI contract is served at `/docs`. Requirements:

- FFmpeg and FFprobe on the PATH.
- `META_API_KEY` for live screening (see `.env.example`). Creating the app loads no credentials and calls no model; starting a screening or fix job calls the Meta Model API in Standard mode and spends credit.
- The cached ASA ruling pages under `data/raw/rulings/`. The committed rulings snapshot holds metadata only, since asa.org.uk states no reuse terms ([source-terms.md](source-terms.md)). With an empty cache the precedent loader fails before any model call. `/health` does not check for the cache. Keep the pages out of git.

Run exactly one worker. The job queue, leases, sessions and sign-in codes live in that process. Deployment to Google Cloud Run is covered in [deploy.md](deploy.md).

## Sign-in and ownership

Without `FIREBASE_PROJECT_ID`, the service runs open and everyone using it shares one workspace. An approval's `by` field is then a name the client supplies.

With `FIREBASE_PROJECT_ID` set, every route needs a session. Sign-in has two steps:

1. `POST /auth/session` with a Firebase ID token. The service checks the account against `PREFLIGHT_ALLOWED_EMAILS` and emails a 6-digit code, valid for 10 minutes. `POST /auth/code/resend` sends another.
2. `POST /auth/code` with the code. The session lasts 12 hours. `GET /auth/me` reports the signed-in account and `POST /auth/logout` ends the session.

Each upload and job then belongs to the account that created it. Another account gets 404 for its IDs on every route, `GET /jobs` lists only the caller's jobs, and an approval's `by` is the signed-in email. For local work without email, `PREFLIGHT_DEV_CODES=1` writes the code to the server log; never set it on a deployment.

## Endpoints

| Method | Path | Behaviour |
|---|---|---|
| GET | `/health` | `ready` when the process is up; says nothing about model access or the rulings cache |
| POST | `/uploads` | One file as the raw request body; returns an opaque upload ID and its expiry |
| POST | `/uploads/parts` | Start an upload sent in parts (below) |
| POST | `/uploads/{id}/parts?offset=` | Send one part |
| POST | `/uploads/{id}/complete` | Finish a part upload and validate it |
| POST | `/screenings` | Queue a screening: `{"upload_id": "...", "title": "...", "align": true}` |
| GET | `/jobs` | The caller's jobs within retention, newest first |
| GET | `/jobs/{id}` | A job's kind and status: `queued`, `running`, `completed`, `incomplete` or `failed` |
| PATCH | `/jobs/{id}` | Rename a job: `{"title": "..."}`, 1 to 120 characters |
| POST | `/jobs/{id}/retry` | Run a failed or incomplete screening again on the same upload; cached stages are reused |
| GET | `/jobs/{id}/events` | Progress as server-sent events |
| GET | `/screenings/{id}` | The source-verified screening JSON, including an incomplete one |
| GET | `/screenings/{id}/report` | The self-contained HTML report |
| POST | `/fixes` | Queue a fix of a screened ad from an editable draft |
| GET | `/fixes/{id}` | The fixed draft, its state, open issues and final screening |
| GET | `/fixes/{id}/stills/{index}` | A still from the fixed draft |
| POST | `/fixes/{id}/approve` | Record a person's approval: `{"by": "Ana", "note": "Reviewed"}` |

`align` turns on word-level timing for the voiceover and defaults to true. The workspace also uses read-only routes under `/ui/` (configuration, results with crops, fix rounds, demos and their reveal), `/uploads/{id}/media` (byte ranges, for video seeking), and the page itself at `/`, `/login` and `/signup`.

POSTs to `/screenings` and `/fixes` return 202 with a job ID. Fetch the result once progress reports a terminal status. A completed screening can still carry flags, so completion alone does not mean a clean result. An incomplete screening can be read and cannot be approved. Every screening read from disk or returned is checked again with `verify_sources`, suggested wording included. Clients cannot submit their own screening JSON or a server path.

## Uploads

Send the file itself as the body with its media type. Multipart is not accepted, so no request spools to a temporary file outside the upload's folder.

```powershell
curl.exe -X POST http://127.0.0.1:8000/uploads -H "Content-Type: image/png" --data-binary "@ad.png"
```

| Input | Media types | Limit |
|---|---|---|
| Image | `image/png`, `image/jpeg`, `image/webp` | 150 MiB |
| Video | `video/mp4`, `video/quicktime` | 150 MiB, 10 minutes (60 seconds in public mode) |
| Script | `text/plain`, `text/markdown` | 64 KiB, 1,000 lines |

WebM is refused because the Model API reads video only as MP4 or MOV. FFmpeg is restricted to local files and these container formats, and an upload is accepted only once a frame decodes. Playlists and URLs are not inputs. The original filename is never kept or used as a path. A refused upload is deleted, and its error names the reason (`unsupported_media_type`, `media_type_mismatch`, `unreadable_media`, `media_too_long`, `empty_upload`, `body_too_large`). `expires_at` is a Unix time in seconds.

### Uploading in parts

Cloud Run refuses requests over 32 MiB, so the workspace sends files over 16 MiB in parts. Any client can do the same:

1. `POST /uploads/parts` with `{"media_type": "video/mp4", "bytes": <file size>}`. It returns `upload_id` and `part_bytes` (16 MiB). The size is checked against the upload limit, and public mode counts this as the file's one upload.
2. `POST /uploads/{upload_id}/parts?offset=<bytes sent so far>` for each part in order, each at most `part_bytes`, as the raw body. It returns `received`. A part at the wrong offset, such as a retried part that already arrived, gets 409 `wrong_offset` with `received`, and the client resumes from there.
3. `POST /uploads/{upload_id}/complete` runs the same checks as a single upload and returns the same fields.

An unfinished upload expires with the normal retention.

## Fixes and approval

A fix needs an editable draft: upload each clean still first and refer to it by upload ID. `screening_id` is the job ID of an API screening.

```json
{
  "screening_id": "<screening job ID>",
  "format": "image",
  "scenes": [{
    "upload_id": "<still upload ID>",
    "on_screen_text": ["<caption>"],
    "voiceover": "",
    "duration_seconds": 4
  }],
  "rounds": 3,
  "align": true
}
```

An image draft has one scene and a video draft up to ten, each 60 seconds at most, with up to three rounds. A voiceover is rendered with local text-to-speech, which needs the `render` extra (`uv sync --extra api --extra render`); the first run downloads a public voice model. Each round replaces flagged lines with register wording, edits a still where a picture carries the claim, and screens the draft again. An edited still is screened like any other input.

The fixed draft's `state` says where the loop stopped: `awaiting_approval` when nothing is flagged, `needs_person` otherwise. Its `decision` stays null until `POST /fixes/{id}/approve` records one, and a second approval is refused. Only a completed draft with nothing flagged can be approved. The approval records a person's review of the draft; it is not a decision by any platform. A script screening has no media to fix, so a fix request on one returns 409 `script_fix_not_supported`.

## Progress

```powershell
curl.exe -N http://127.0.0.1:8000/jobs/<job ID>/events
```

Events are `event: progress` with increasing numeric IDs and JSON data. A screening reports each stage as it finishes; a fix reports queued, running and its terminal state. Events carry status metadata only, never ad text, evidence or notes. Reconnect with `Last-Event-ID` to receive the events after it; an invalid ID returns 400. The stream closes when the job ends. A job left unfinished by a restart becomes `failed` with `worker_interrupted`, so model calls that may have been billed are never repeated silently.

## Script input

Upload UTF-8 `.txt` or `.md` copy as `text/plain` or `text/markdown`, then start a screening as usual:

```powershell
curl.exe -X POST http://127.0.0.1:8000/uploads -H "Content-Type: text/plain" --data-binary "@script.txt"
```

A UTF-8 byte-order mark and LF or CRLF line endings are accepted. Lines keep their physical numbers, blank lines included, and non-blank lines are kept exactly. A line starting `VO:` is spoken and one starting `SUPER:` is on screen (either case); other lines are unlabelled. Markdown is read as literal text, and links or HTML in it are never fetched or run. Invalid UTF-8, binary control characters and whitespace-only files fail before any model call, with an error code that quotes nothing from the file.

A script skips transcription, on-screen reading and region detection, and goes straight to claim extraction and the check. The screening has `ad.media = "script"`, the numbered `script_lines`, and evidence of kind `script` holding the line number and the line's exact text. Scripts have no frame dimensions or timestamps, so a client must check `ad.media` before reading dimensions. Every script result states that only the script was screened and the finished ad needs its own screening. The command line takes the same files: `uv run preflight screen script.txt --no-align`. Text previews are served as `text/plain` with `nosniff`.

## Public mode

`PREFLIGHT_PUBLIC_MODE=on` applies limits for an open demo. Each visitor may make 10 uploads, 3 screenings and 1 fix per hour, counted per account when signed in and per client address otherwise; a fix runs one round; video is limited to 60 seconds. Model spend across all visitors is capped per day (`PREFLIGHT_DAILY_CAP_USD`, default 40) and recorded in `spend.json` under the storage root. An approval made in public mode is marked `public_demo`. `PREFLIGHT_PUBLIC_MODE=replay` refuses new uploads, so only the preloaded demos run. A request over a limit gets 429 `rate_limited` with the limit's `kind`, its `limit` and `retry_after` in seconds, which is also sent as a `Retry-After` header. `GET /ui/allowance` returns what each limit has left and when it resets. Once the cap is reached, or in replay mode, new work gets 503 `daily_cap_reached` or `uploads_paused`. The mode is read from the environment, so changing it takes a restart.

## Retention and errors

Each upload lives in `data/raw/uploads/<opaque ID>/` and is kept for 24 hours. The source file, frames and audio, model cache, screening JSON, fix outputs, render files and the fix audit all stay inside that folder. Retention covers this service's storage only; the model provider's own retention is separate.

Expired uploads are removed at startup and by a sweep every 30 seconds. A running job keeps its inputs until it ends, for at most an hour past their expiry; a job still running then fails with `expired_while_running` and its data is deleted. Screening the same upload again reuses its model cache. A fix that draws on several uploads expires with the earliest. Expired data cannot be read or used to start a job. The retention journal holds opaque IDs, times and storage events only, never a filename, caption, approval name or note; a failed deletion is logged and retried.

`create_app` accepts `Settings(root=..., retention_seconds=..., ...)` for local configuration and tests. Other defaults: 256 KiB per JSON body, two worker threads and 16 pending jobs.

Error bodies carry a short code and the screening notice, and never echo the input or a worker's exception. Responses are sent with `Cache-Control: no-store`.

| Status | Meaning |
|---|---|
| 400 | Invalid event ID or sign-in code |
| 401, 403 | No valid sign-in, or an account not on the allowlist |
| 404, 410 | Unknown resource, or one past its retention |
| 409 | Result or decision not available yet, wrong part offset, or an action the job's state does not allow |
| 413 | Body over its limit |
| 415 | Unsupported, mismatched or unreadable media, or a script that is not valid UTF-8 text |
| 422 | Invalid request, empty upload, media too long, or a script with no ad copy or too many lines |
| 429 | Job queue full, or a public-mode or sign-in rate limit |
| 503 | Web build missing, workers unavailable, email codes not configured, or public-mode uploads closed |

## Tests

```powershell
uv run --offline pytest tests/test_api.py tests/test_web_api.py -q
uv run --offline pytest -m "not live"
uv run --offline ruff check
```

The API tests run in process through real HTTP routing, lifespan and server-sent events. Screenings replay recorded synthetic model responses over transports that refuse network access, and fixes replay recorded rounds through the real fix and approval logic. They cover expiry, failed deletions, active leases, restarts, request limits, invalid media, error privacy, forged wording and approval. They test the contract; they say nothing about live model accuracy, which is measured as described in [evaluation.md](evaluation.md).
