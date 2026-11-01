# P52 user verification — 1 November 2026

## Presentation follow-up

After the P52 implementation was committed as `dd0ba9b`, a separate frontend
presentation pass implemented the [approved design direction](../notes/p52-design-research.md).
This follow-up remains uncommitted. It adds dark/light appearance, a compact loaded
workspace, recorded-evidence time-axis lanes, dedicated editor/comparison views
and exact changed-line highlighting between any two saved rounds. No API,
model, schema, source, evaluation or decision-eligibility logic changed.

On the same retained synthetic video at 1511 × 870, video y=1018 became y=458,
and the claim inspector begins at y=441. The first desktop viewport now shows the
creative and selected claim together. This demonstrates placement, not improved
task-completion time; no independent user study has been conducted.

Current verification:

- `npm --prefix web run build`: generated types, TypeScript and production build passed.
- `npm --prefix web run test:browser -- tests/presentation.spec.ts`: 3 passed.
- `npm --prefix web run test:browser`: 12 passed, including the existing recovery
  suite and complete synthetic upload/fix/review/reload workflow.
- `npm --prefix web test`: 6 passed.
- `npm --prefix web run format:check`: passed.
- `uv run --offline pytest tests/test_web_api.py -q`: 13 passed.
- `uv run --offline pytest -m "not live" -rs`: 343 passed, 2 skipped, 5 deselected.
- `uv run --offline ruff check`: passed.
- `uv run --offline python scripts/verify_agent_setup.py`: passed.
- `tooling/node_modules/.bin/openspec.cmd validate p52-web --strict`: valid.

New browser coverage checks desktop media placement, theme changes without losing
selection, text contrast for five token pairs in both themes, keyboard time-axis
selection and seek, mobile evidence/editor/comparison overflow, doubled CSS content
scale and round swapping. CSS scaling approximates magnification; it is not an
exhaustive browser/assistive-technology accessibility audit. A contrast-test parser
initially rejected minified three-digit hex colours; the helper now handles both
three- and six-digit hex and the checks pass. The existing report-link assertion
also caught a link hidden by the new editor view; the runtime link was moved into
the shared result header and the complete workflow passes.
The final repeat also exposed a test starting a programmatic upload before config
loaded. Upload scenarios now wait for the enabled input, matching the actual user
interaction rather than bypassing its disabled state.
Async completion assertions also use the existing workflow's 30-second budget;
one repeat found the synthetic pipeline still legitimately running after the
default five-second assertion window. Recovery assertions retain their tighter
timeouts, and no test retries or skipped scenarios were introduced.

The rebuilt normal app runs on localhost port 8002. Retained live synthetic video
evidence still seeks to 0.14 seconds; the real image-fix comparison shows the exact
old/new caption and leaves the human decision untouched. No new paid model call
was needed for this presentation pass. Screenshots under ignored
`data/work/verification/p52-redesign/` were visually inspected in both appearances
and at mobile width. The final P33/P53 and voiced-video-fix limits below still apply.
No full WCAG certification, cross-browser certification or competition readiness
is inferred from these tests.

## Initial implementation verification

At the initial review, the uncommitted P52 workspace on `adi-branch` passed the checks below.
This review exercised the production frontend against real Uvicorn, both with
network-blocked recordings and with live synthetic image/video inputs. It found
and corrected seven defects; it does not establish model accuracy or completion
of the final competition acceptance criteria.

## Findings corrected

Each correction was checked with a regression that failed before the fix.

| Finding | Resulting behavior |
| --- | --- |
| Malformed SSE JSON left the workspace permanently busy | Invalid progress closes the stream, shows a recovery message and releases controls; reloading the retained job works. |
| Delayed demo reveal could populate a different selected demo | Selection generation guards reject stale reveal responses. |
| Starting another ad retained the previous draft editor values | Captions, voiceover, format and selected still reset with the job. |
| Malformed final-run CSV broke the entire config request | Invalid registry data makes the scoreboard unavailable while upload remains usable. |
| Malformed demo manifests caused an uncontrolled server error | Manifest structure is validated and returns a controlled `409 invalid_demo_manifest`. |
| Timestamp rounding could display `0:60.0` | Tenths round before minutes/seconds are separated. |
| Long unbroken demo titles overflowed narrow screens | Titles wrap within their containers, including a 390-pixel viewport. |

Native EventSource reconnect was also tested by dropping the stream. The browser
resumed event IDs without duplicates and completed the result. No reconnect
implementation change was necessary. Old stream callbacks cannot update a newer job.

## Automated checks

| Command | Result |
| --- | --- |
| `uv run --offline pytest tests/test_web_api.py -q` | 13 passed |
| `uv run --offline pytest -m "not live" -rs` | 343 passed, 2 skipped, 5 deselected |
| `uv run --offline ruff check` | Passed |
| `uv run --offline python scripts/verify_agent_setup.py` | Passed |
| `npm --prefix web run build` | Generated types, TypeScript and production build passed |
| `npm --prefix web test` | 6 passed |
| `npm --prefix web run test:browser` | 9 passed |
| `npm --prefix web run format:check` | Passed |
| `npm --prefix web audit` | 0 vulnerabilities; workstation system CA enabled |
| `tooling/node_modules/.bin/openspec.cmd validate p52-web --strict` | Valid |
| `git diff --check` | Passed |

The two Python skips are Windows symlink permission and optional torchaudio. The
five live-marked tests were not included in the offline suite; separate live smoke
evidence follows. Editor diagnostics were clear for the changed runtime/test files.

The nine Chromium browser scenarios cover demo evidence and reveal, upload and
SSE without progress polling, timeline seeking, rendered fix history, explicit
synthetic review and reload, invalid media, mobile layout, malformed progress,
stale reveal, editor reset, expired jobs, disconnect recovery and long titles.
Recordings are labelled and model transports reject network. Synthetic review
records exercise the decision path without deciding whether a real ad may run.

## Live synthetic user checks

The normal app was rebuilt and restarted on localhost port 8002. The user's
existing port 8000 server was preserved. The restored public-source index contains
the expected 33 eligible precedents; repository source validation passed. These
examples are smoke checks, not benchmark examples or final evaluation measurements.

- Image screening `425d7aed53514f4e98bbd2cea0e8aaa3` completed with two
  source-verified flags on the synthetic fatigue caption.
- Image fix `95c9c1296f194bd1a25997c0d47206a4` rendered and screened two rounds.
  The first had three flags; the next completed with zero flags and the exact
  suggested register caption. Reload retained both rounds. It remains
  `awaiting_approval`, with no human decision recorded.
- Video screening `5c843a6e9b5940c696fae5251bc8847c` completed transcription,
  region extraction, on-screen extraction, claims and checking. It returned seven
  claims and five flags; all source references passed `verify_sources`.
  The three-second synthetic input combined the existing magnesium image and
  separate vitamin-D speech fixture deliberately; it is not a coherent final ad.
  Selecting the spoken claim sought the actual browser video to 0.14 seconds;
  media readiness was 4 with no playback error. The page showed turn-level timing,
  the spoken evidence and dated source provenance. Its full-page screenshot was
  visually inspected. Image/crop presentation and seeking also pass browser tests.

Ignored local receipts are under `data/work/verification/p52-live/` and
`data/work/verification/p52-user-review/`, including source-verified video JSON,
stage events, report and screenshot. No customer media, credentials, private model
caches or generated run receipts were added to source control.

## Remaining limits and next step

P33 must supply the selected registered final test run and P53 must supply the
final demo reconstructions. Neither exists here; the workspace reports their
absence rather than substituting synthetic metrics. A live voiced-video **fix**
with the optional rendering/voice stack still needs a separate check. Live video
screening and the live image fix are verified, but that does not cover this path.

This is a localhost, single-process prototype without authenticated identities.
Public deployment, Linux CI execution, Firefox/WebKit and exhaustive accessibility
testing were outside this check. Graphify is stale relative to dev/P52. No model
prompts, policy wording, frozen splits, held-out labels or final results changed.

The next useful step is to supply the final P53 assets and P33 run, then rehearse
the exact competition flow and verify the optional voiced-video fix if it is used.
All changes remain uncommitted; no push or deployment was performed.
