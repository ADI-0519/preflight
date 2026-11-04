# PR82 versus current dev

Compared dev `33535b8` with PR82 head `e642e48`, using their shared base
`242978d` to distinguish the PR's changes from subsequent dev work. PR82 is open
and GitHub reports merge conflicts. Work remains on `p43-open-weights-triage`.

## Decision

Keep the concrete fixes below. Do not merge PR82 wholesale or resolve conflicts
by selecting all of one side. Much of its extra material is historical tooling,
and its blanket ban on registered subsets conflicts with the newer P60 decision
allowing an explicitly identified development cohort.

| Area in PR82 | Current dev | Decision and implementation |
| --- | --- | --- |
| ASR HTTP client cleanup | Only SDK clients closed | Ported cleanup on success/failure, deduplicating shared SDK instances. |
| Windows transcription TLS trust | Default CA setup fails on this machine | Ported system trust context; hostname/certificate verification remains enabled. |
| Missing main preview and revision retry tests | Main preview lacks failure fallback | Ported per-media fallback/reset and browser checks for usable claims, another demo, refused revision and retry. |
| Pinned precedent loading | Scans raw pages before exclusions; missing eligible pages can change the corpus | Select eligible metadata before reading pages; require pinned files and matching ID/date/advertiser, reject duplicate IDs, validate content fingerprints when present. |
| Rescore provenance | Media-count guard exists, but hyphenated media stems are split incorrectly | Preserve original cohorts as dev grows; match manifest ID prefixes, require every media part, reject failed/incomplete or source-mismatched saved screenings. |
| CLI selection and dirty revisions | Unknown selections silently disappear; empty `--only` means all items; untracked sources ignored | Reject invalid/empty/overlapping selections before inputs/clients; include untracked source files in dirty status. |
| Subset registration ban | Newer P60 decision permits named cohorts | Do not port. Valid subsets still register with their original item lists; final test still runs whole. |
| P32 legacy predictor and runner | Upstream v2 comparator and registered dev comparison exist | Do not add another comparator. Retain current canonical implementation and results. |
| P33/P70 review exporters and strict judge receipts | Optional local audit utilities, dependent on saved bundles | Defer rather than make them dependencies of screening or rewrite completed human review records. |
| 115-entry corpus candidate, retrieval floor experiments, new crawler retry machinery | Adopted corpus is 114 entries; retrieval policy and floor are already selected | Do not port the alternate candidate or change retrieval choices. Crawler hardening can be separate work when needed. |
| Interval-method registry column/shared text-baseline abstraction | Current exact intervals and shared model scorer exist | Optional provenance/convenience additions; no new CSV migration or duplicate scoring API in this fix. |
| Archive/navigation cleanup and old research/review notes | Historical context, not a missing runtime capability | Preserve in the original branch/PR; do not import the document inventory into this branch. |

Dev's public-mode notices, upload/rate/spend/fix limits, frozen v2, updated
independent checks, image-cost metering and `store=False` remain intact. A
two-tip diff shows these newer dev features as absent from the older PR; that
does not mean the PR explicitly deleted them. Its actual changes must be judged
relative to the shared base. No labels, split membership, prompts used for
judging, registered metrics or adopted snapshot files were changed here.

Fingerprint validation is conditional: old snapshot rows have no content hash.
Their source identity/date/advertiser are checked, but that cannot establish
that their full wording is identical to the original download. Do not fabricate
historical fingerprints by stamping current pages as their original content.

## Verification

Eight regression cases reproduced the missing behaviors before the port. The
expanded suite also checks source drift/missing pages/duplicates, valid original
cohorts, all four evaluation CLIs, source/client lifecycle and TLS settings.

- `uv run --offline pytest -m "not live" -q --basetemp "$gapTestRoot"`:
  **526 passed, 2 skipped, 7 deselected**. `$gapTestRoot` was a fresh short path
  under `C:/Users/adirj/AppData/Local/Temp/pfgap-<unique>`; long Windows agent temp
  paths cause existing FFmpeg failures. Skips are optional alignment and Windows
  symlink capability. A prior test stub was updated to use the real Split type
  so the new selection invariant is exercised rather than bypassed.
- `uv run --offline pytest tests/test_triage.py tests/test_triage_eval.py -m live -s --tb=short`:
  **2 passed** against Baseten `meta-models/muse-spark-open-1026`, including a
  synthetic source-load/classify/match/report workflow. This is not dev recall.
- VS Code task `Build PreFlight web` (`npm --prefix web run build`): passed,
  including generated types and TypeScript checks.
- `npm --prefix web test`: **8 passed**.
- `npm --prefix web run test:browser`: **19 passed**, using real Uvicorn/HTTP,
  network-blocked synthetic recordings, mobile/keyboard/reload/error workflows.
- `uv run --offline ruff check`, `npm --prefix web run format:check`,
  `.venv/Scripts/python.exe scripts/verify_agent_setup.py`, editor diagnostics,
  `git diff --check` and the generated-type diff check: passed.

## Fresh live user walkthrough

Started a separate public-mode Uvicorn server on port 8014, with isolated ignored
uploads and real Standard-mode Meta clients. Uploaded the existing synthetic
video/audio through the browser's file picker. Job
`54d96d1df49e47eba3a2daab388c10ee` completed all five stages and returned one flag
with timed evidence, register wording and source provenance. Its three-second
speech fixture ends mid-sentence; this outcome is not evidence of false-alarm
performance on a complete authorised claim.

Used the revision form with the committed text-free synthetic tablet still and
the exact repository register wording, "Vitamin D contributes to the normal
function of the immune system". Live fix job
`e334760ea1ef46c6965e6acad2c16542` rendered/re-screened the supplied draft and
returned zero flags at round 0. The result survived browser reload, the source
report returned HTTP 200, and a 390px viewport had no horizontal overflow.
The review-decision button remained disabled without the person's details and
confirmation. No human approval was recorded.

The original page and the fresh result use different jobs/servers; old shared
tabs are not proof that the current code ran. This walkthrough and the browser
suite are agent-operated tests, not independent human usability research.

## Remaining work

P43's real v2 dev measurement still needs the retained screenings for a registered
dev run. No held-out ad copy was inspected for tuning and no final test evaluation
was run. The source Graphify output was queried and remains historical. The live
server can be inspected at `http://127.0.0.1:8014/?job=e334760ea1ef46c6965e6acad2c16542`.
Changes are local; this audit does not merge/close PR82, commit, push or deploy.
