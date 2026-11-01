# Local screening API (P51, issue #27)

The API delegates screening and fixing to the existing pipeline and P41 agent.
It records human decisions; it does not decide whether Meta will allow an ad.

## Run

```powershell
uv sync --locked --extra api --extra page
uv run --extra api uvicorn preflight.api:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

FFmpeg and FFprobe must be on PATH. Open `/docs` for the typed OpenAPI contract.
Live screening also needs the team's cached ASA ruling HTML pages under
`data/raw/rulings/`, including the older eligible precedents. The committed ruling
snapshots contain metadata only. With an empty cache, the precedent loader fails
before model screening; `/health` alone does not verify this prerequisite. Keep
downloaded ruling pages ignored rather than adding them to Git.
The service is a local, single-process prototype. It has no user authentication or
tenant isolation. Keep it bound to localhost; production access needs separate work.
An approval's `by` value is a person's supplied name, not an authenticated identity.

Creating or starting the app does not load credentials or call a model. Starting a
screen/fix job uses the configured Standard-mode clients and can consume model credit.
Live calls were not used to verify P51. Langfuse instrumentation is not enabled.

## Endpoints

| Method | Path | Behavior |
|---|---|---|
| GET | `/health` | Service liveness, not proof of model/account availability |
| POST | `/uploads` | Stream one raw image/video body; return opaque upload ID and expiry |
| POST | `/screenings` | Queue `screen()` for `{ "upload_id": "...", "align": false }` |
| GET | `/jobs/{id}` | Job kind/status: queued, running, completed, incomplete or failed |
| GET | `/jobs/{id}/events` | Ordered metadata-only SSE progress; supports Last-Event-ID |
| GET | `/screenings/{id}` | Source-verified Screening, including an incomplete result if available |
| GET | `/screenings/{id}/report` | Existing self-contained HTML report with evidence and source links |
| POST | `/fixes` | Queue P41 `fix()` from a retained screening and draft assets |
| GET | `/fixes/{id}` | Updated script/captions, open issues and source-verified screening |
| GET | `/fixes/{id}/stills/{index}` | Retained still preview referenced by the fixed draft |
| POST | `/fixes/{id}/approve` | Call P41 `approve()` with `{ "by": "Ana", "note": "Reviewed" }` |

Upload `expires_at` values are Unix timestamps in seconds (UTC).
Screening/fix POSTs return 202 plus a job ID. Fetch results only after progress reports
a terminal status. A completed job can contain flags; completion is not a clean result.
An incomplete screening is still inspectable and cannot be approved. A fix ends in
`awaiting_approval` or `needs_person`; a separate explicit approval call is required.
Repeated approval is rejected. Every screening accepted from disk or returned is
revalidated with `verify_sources`, including suggested wording. Clients cannot submit
a replacement Screening JSON or arbitrary server paths.

The fixed draft's `state` records where the fix loop stopped. Its separate `decision`
field is null until the explicit approval call and then carries the persisted human
decision, including after a page reload. It is not a platform-enforcement decision.

### Upload

Send the file itself as the body, with its media Content-Type. Do not use multipart.
This avoids multipart's temporary-file spooling outside the retained directory.

```powershell
curl.exe -X POST http://127.0.0.1:8000/uploads -H "Content-Type: image/png" --data-binary "@synthetic-ad.png"
```

Supported types: PNG, JPEG, WebP, MP4, WebM and QuickTime. Validation restricts FFmpeg's
input formats/protocols and checks that a frame decodes. Playlists and URLs are not
supported inputs. Defaults: 100 MiB per upload, 256 KiB for JSON bodies, ten minutes
maximum media duration, two worker threads and sixteen pending jobs. No original
filename is retained or used as a path. Oversized/failed uploads are discarded.

### Fix

Upload each still first. Use upload IDs in the draft; the API resolves them within
private storage. The screening ID below is the API screening job ID, not an arbitrary
client-supplied screening. P41 re-screens the editable draft as its first round.

```json
{
  "screening_id": "<screening-job-id>",
  "format": "image",
  "scenes": [{
    "upload_id": "<still-upload-id>",
    "on_screen_text": ["<draft caption>"],
    "voiceover": "",
    "duration_seconds": 4
  }],
  "rounds": 3,
  "align": false
}
```

Image drafts have one scene; video drafts have up to ten. A voiceover can require the
existing local TTS tooling and voice assets; that remains P41's rendering dependency.
Install its optional dependencies with
`uv sync --locked --extra api --extra page --group fixtures` before using video
voiceovers. P41's first voice setup can download its public voice model.
Generated stills are re-screened by P41. The API never trusts a regenerated image as
having no issues. Register replacements and remaining issues are in the existing fix
audit. Still previews use URLs; server filesystem paths are not returned.

### Progress

```powershell
curl.exe -N http://127.0.0.1:8000/jobs/<job-id>/events
```

Events use `event: progress`, increasing numeric IDs and JSON data. Screening events
include finished stage/status metadata; fix events currently expose queued, running
and terminal states. No ad text, source evidence or actor notes are included in SSE.
Reconnect with `Last-Event-ID` to retrieve subsequent events. Streams close when the
job finishes; a later approval can be retrieved by reconnecting. Invalid event IDs
return 400. Restarted unfinished jobs become failed with `worker_interrupted`; the
service does not silently repeat potentially billed model calls.

## Retention and errors

Default storage is `data/raw/uploads/<opaque-id>/`; default retention is 24 hours.
The source, ingestion frames/audio, model caches, screening JSON, fix outputs,
rendering temporary files and private fix audits all stay beneath that tree. API
retention covers local storage, not the model provider's separate retention policy.
All clients use the existing Standard-mode model guard.

Startup and a 30-second background sweep remove expired uploads. Active jobs pin
their inputs until processing ends, for at most an hour past expiry
(`job_grace_seconds`); a job still running then is failed with
`expired_while_running` and its data deleted. A multi-upload fix expires with its earliest
input, including when deletion must be retried after that input has already gone.
Expired data cannot be retrieved or used to start another job. The retention journal
contains only opaque IDs, timestamps and storage/deletion events; failed deletions
are recorded and retried. It contains no filename, caption, approval name or note.

The app factory accepts `Settings(root=..., retention_seconds=..., ...)` for local
configuration and isolated tests. Run one server worker: the queue/leases are local
to that process. Filesystem backups and remote-provider storage are not managed here.

Public error bodies contain generic codes and the screening notice. Validation does
not echo private input, and worker exceptions are not included in events or info logs.
HTTP statuses include 413 for body limits, 415 for unsupported/unreadable media, 422
for invalid request structure, 404/410 for unavailable/expired resources, 409 for an
unavailable result/decision and 429 when the job queue is full. Responses use no-store.

## Verification

```powershell
uv run --offline pytest tests/test_api.py tests/test_agent.py tests/test_pipeline.py tests/test_ingest.py -q
uv run --offline ruff check
uv run --offline pytest -m "not live"
uv run --offline python scripts/verify_agent_setup.py
```

API tests run in-process through real HTTP routing/lifespan/SSE. Screening uses the
existing recorded synthetic model responses with HTTP transports that reject network.
Those recordings combine a clip with a separate speech fixture, as in the offline
replay command; they are a contract test, not evidence of single-upload live accuracy.
Fix tests replay P41's recorded synthetic rounds through the real fix/approval logic.
CI installs the API extra. Tests cover expiry, failed-deletion retries, active leases,
restart, request limits, invalid media, private errors, forged wording and approval.
