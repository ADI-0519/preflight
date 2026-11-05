# Tasks

Task status below records verified work. The user confirmed all-founder agreement on 3 Nov 2026;
the corresponding product-rule interpretation and dated decision are recorded under task 1.1.

## 1. Product decision and compatibility contract

- [x] 1.1 Obtain confirmation of all three founders' agreement to quoted, numbered script-line evidence; document the agreed contract in `docs/api.md` and the corresponding rule-3 clarification in `docs/product-rules.md`, preserving media evidence requirements. Retain the original confirmation record separately rather than attributing an unconfirmed decision.
- [x] 1.2 Add schema-v4 script metadata, source lines and evidence validation, and document the new contract in `docs/architecture.md`. Verify exact text/line matching, cross-mode rejection and valid v1/v2/v3 media reads with focused schema tests. Normalise the pre-integration P72-v3 script variant to v4 on read.
- [x] 1.3 Regenerate `web/schema.json` and `web/src/screening.d.ts`; verify schema generation and `npm --prefix web run check` pass and generated files match the Python schema.

## 2. Deterministic ingestion and shared screening

- [x] 2.1 Add bounded UTF-8 script ingestion and optional VO/SUPER parsing. Verify BOM, LF/CRLF, blank-line gaps, literal markdown, Unicode, empty input, invalid UTF-8, binary control content and size/line limits with synthetic tests; document the accepted input grammar in `docs/api.md`.
- [x] 2.2 Extend evidence preparation and the existing extraction path for text-only script requests, without altering media prompt bytes. Verify returned citations resolve only to supplied source lines, joined claims cite their pieces, and script content cannot create out-of-scope evidence IDs.
- [x] 2.3 Dispatch script inputs through `pipeline.screen` with perception stages skipped. Verify transcribe/on-screen/region/image clients raise if invoked, no media is fabricated, no-claim checks finish and failures remain incomplete; update the architecture description in `docs/architecture.md`.

## 3. CLI, tool and report delivery

- [x] 3.1 Extend CLI path dispatch and `screen_ad` through the shared path. Verify a synthetic `.txt` and `.md` script produce schema-valid results with source-backed flags and quoted numbered evidence, and that an existing media replay still passes; document CLI examples in `README.md`.
- [x] 3.2 Add script evidence to shared views, HTML reports and tool text, with explicit script-only result wording and a finished-ad-check notice. Verify escaping, source provenance, exact register suggestions, zero-flag wording and incomplete wording with report/view/tool tests.
- [x] 3.3 Guard media fix/regeneration paths for scripts. Verify unsupported direct requests fail explicitly and cannot produce a finished-ad approval from a script-only result.

## 4. API and retention

- [x] 4.1 Add text/plain and text/markdown uploads using shared script validation and limits before job creation. Verify valid uploads, mismatched/binary content, oversized scripts and bounded errors with API tests, with no FFmpeg or inference on rejected inputs; update `docs/api.md`.
- [x] 4.2 Extend script job execution, preview/report and progress through existing private upload storage. Verify opaque responses, content-free events/logs, expiry of source/derivatives/cache, public-mode quotas, restart behaviour and source-file path containment with API/storage integration tests.

## 5. Web review experience

- [x] 5.1 Accept script files and display numbered source text, flag-to-line navigation and script-only scope. Verify React text escaping, no media player dependence, no media-fix controls and continued media result rendering with component/type checks.
- [x] 5.2 Add synthetic script replay fixtures and browser scenarios for upload, stage progress, flag selection, exact sources, report download, saved-result reload, incomplete result and narrow viewport. Run them against a fresh local Uvicorn instance with live network calls blocked; document actual browser outcomes in `docs/api.md` without claiming screening accuracy.

## 6. Paired development evaluation

- [x] 6.1 Add dev-only script fixture export from original shot-list ad words and authored team copy, with source hashes and line mappings. Verify no image prompts, assessment text, label annotations or held-out items enter scripts.
- [x] 6.2 Add original-baseline cohort validation and paired metrics/registration. Verify missing/void/test/incomplete inputs fail before labels or clients, textual-population masks and denominators are explicit, failed checks cannot register success and historical result files remain unchanged.
- [ ] 6.3 Obtain retained baseline screenings and original dev inputs, then run the authorised script-versus-media comparison and record its run IDs, cohort, configuration, counts and limitations in `docs/evaluation.md`. Verify every issue acceptance criterion against the actual registered artifacts; leave this task pending if inputs or authorisation are absent.
  - 3 Nov check: `screen-20261103T172541` is registered, but `data/work/runs/screen-20261103T172541` is absent. `--check-inputs` stopped before model client construction; leave the comparison pending.

## 7. Final integration checks

- [x] 7.1 Run focused changed-area tests, then `uv run ruff check`, `uv run pytest -m "not live"` and `python scripts/verify_agent_setup.py`; record exact results and skips, using a short unique temporary test directory where required by FFmpeg fixtures.
- [x] 7.2 Run the web build, unit checks and browser suite against the completed contracts. Perform the fresh user walkthrough in 5.2 and a media regression; record replay/live distinctions, unexpected client calls and unverified risks.
- [x] 7.3 Review source/provenance, wording, customer retention and evaluation boundaries with the applicable project skills; validate this OpenSpec change and inspect the final diff for generated contract drift and secrets before any requested commit or push.

## Workflow follow-up

- Keep P72 open until the founder decision, all delivery paths and the registered dev comparison are complete.
- Sync main specs and archive this change only after implementation and required review are complete.
- Deployment, publication, organiser messages and the final held-out test remain separate actions.
