# Design

## Context

Issue #27 owns the API contract. P41's fix loop was merged at ab3b4b3, retaining our
screening and evaluation safeguards. The pipeline previously offered no progress hook.

## Goals / Non-Goals

Provide a local single-process HTTP service with persisted job status, source-verified
results and bounded private storage. No accounts, public deployment, distributed queue,
frontend, external telemetry or live evaluation is introduced.

## Decisions

- Stream a raw file request body, with its media Content-Type, rather than multipart.
  This avoids multipart spooling outside the retained directory. MIME and actual media
  type are checked; client filenames and local paths are never accepted.
- Use opaque upload/job IDs, a small thread pool and a bounded pending queue. Persist
  status/events alongside each upload; on restart mark unfinished jobs failed instead
  of repeating potentially billed calls. A distributed broker is unnecessary here.
- The API delegates to screen/fix/approve. Optional stage callbacks carry StageRun
  metadata only. SSE IDs are ordered, replayable and independent of ad content.
- Fix requests reference a server-owned screening and retained still IDs. All stored
  screenings are revalidated with verify_sources before use or return. Clients never
  supply arbitrary paths or replace a server-owned screening body.
- Store derivatives, caches, results, rendered drafts and private audits beneath
  data/raw/uploads/<id>. A retention journal outside individual folders holds only
  opaque IDs, timestamps and storage/deletion events. A background sweep and startup
  sweep enforce expiry; running jobs pin all referenced uploads.
- Expiring any input invalidates a multi-upload fix and removes its derived job data.
  Model caches are per job. Draft rendering uses its output directory for temporary
  files rather than the global temporary directory.
- Approval records a supplied human name; it does not authenticate identity or claim
  Meta approval. Incomplete, flagged and already-decided results cannot be approved.

## Risks / Trade-offs

- Single-process state -> run one uvicorn worker; production isolation/authentication
  requires a separate design before exposing the service to untrusted networks.
- Filesystem deletion can fail -> retain a content-free failure event and retry.
- Windows FFmpeg paths can be long -> keep private storage roots short and test with
  a short synthetic temporary root; operational failures remain generic to clients.
- Local replay does not establish live accuracy -> do not call live models during
  verification; preserve recorded-response limitations in the test documentation.

## Migration Plan

Install the optional api extra, run the documented localhost factory command and use
the HTTP docs. Existing CLI and schema remain compatible. Stop the local server to
roll back; retained directories remain subject to the configured startup sweep.
