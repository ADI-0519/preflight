# Proposal

## Why

GitHub issue #27 (P51) needs an HTTP boundary around the existing screening and fix
pipeline so the planned web page can upload, follow progress, inspect and approve.
Confidential uploads also need an enforced, testable retention lifecycle.

## What Changes

- Add upload, screening, fix, retrieval, SSE and explicit human-approval endpoints.
- Keep uploads and all derived private artifacts in one retained storage tree.
- Validate source provenance at API boundaries and preserve incomplete results.
- Add replay-backed HTTP tests and retention/restart/error regressions.

## Capabilities

### New Capabilities

- `screening-api`: HTTP jobs, progress, screening/fix results and human approval.
- `upload-retention`: Bounded private uploads, automatic expiry and deletion audit.

### Modified Capabilities

None.

## Impact

New preflight.api modules, FastAPI/uvicorn optional dependencies, tests and API docs.
Reuse preflight.pipeline.screen and preflight.agent.fix/approve after merging P41.
Only a minimal progress callback is added to the pipeline. No frontend, deployment,
multi-user authentication, live-model execution or evaluation-data changes are in scope.
