## Why

Issue #28 requires a usable React workspace over P51: a claim must connect to its
evidence and sources, fixes need visible round history, and demo outcomes and final
metrics must remain distinct from screening and development measurements.

## What Changes

- Add a Vite/TypeScript React page served by FastAPI, using schema-generated types.
- Upload media, receive persisted SSE progress, seek claim evidence, display exact
  source provenance and register wording, and reload retained job results.
- Add read-only media/range, crop, verified presentation and fix-round endpoints.
- Present explicit human review only for complete, unflagged final fixes.
- Read explicitly configured demo assets and reveal ASA metadata on request.
- Read the selected final test run from the native registry; show unavailable when
  no valid selection exists. Add offline browser tests and CI build gates.

## Capabilities

### New Capabilities
- `screening-workspace`: browser upload, evidence navigation and human review.
- `demo-presentation`: labelled assets, separate outcome reveal and registered metrics.

### Modified Capabilities

None. The existing Screening schema, policy sources, prompts and evaluation protocol
remain unchanged. Read-only P51 additions support the page.

## Impact

New optional Node build under web/, additive local API routes, source-confined media
reads, and CI frontend checks. P33 still owns final evaluation; P53 owns final asset
selection. No accounts, public deployment, model tuning or publishing is added.
