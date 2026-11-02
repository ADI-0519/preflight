# Tasks

## 1. Private upload lifecycle
- [x] 1.1 Implement bounded raw uploads, private per-upload storage and retention journal; test limits, invalid media and deletion.
- [x] 1.2 Enforce startup/periodic expiry and active-job leases; test restart and processing/expiry races; document retention boundaries.

## 2. Screening jobs and progress
- [x] 2.1 Delegate screening through the pipeline with source verification and metadata-only stage callbacks; pass replay-backed HTTP tests.
- [x] 2.2 Persist ordered SSE events and terminal outcomes; test reconnect, incomplete results and redacted errors; document endpoints.

## 3. Fix and human review
- [x] 3.1 Bind draft assets to retained upload IDs and reuse P41 fix; test recorded rounds, invalid sources and private path isolation.
- [x] 3.2 Reuse P41 approval with complete-check guards; test explicit approval, failed/skipped checks and repeated decisions; document the human-only meaning.

## 4. Integration checks
- [x] 4.1 Run focused regressions, full non-live tests, Ruff, schema/setup checks and OpenSpec validation; record evidence and limitations.
- [x] 4.2 Add API dependencies to CI and update the API guide, plan and handoff.
