# Proposal

## Why

P72 (historical issue #84 from the source project) lets an advertiser find possible claim issues
in a script before paying to produce the ad. A separate check of the finished ad remains necessary because
scripts cannot establish what the final pictures, captions or delivery imply.

## What Changes

- Add plain UTF-8 `.txt` and `.md` scripts as a first-class input, retaining physical line numbers and optional
  `VO:`/`SUPER:` channel hints. Markdown is text, not executable or fetched content.
- Add schema-v4 script-line evidence and script input metadata. Preserve readable v1/v2/v3 media results and
  the existing timestamp/region evidence requirements for images, videos and pages.
- Route scripts through the existing `pipeline.screen`, claim parser and checker; skip perception stages
  and make no transcription, visual-reading, region or image calls for script inputs.
- Expose this input through the existing CLI, upload API, web workspace and `screen_ad` tool. Reports show
  the exact quoted script line and number, and explicitly limit the result to the script.
- Apply per-upload retention, public quotas, size limits and metadata-only logging to scripts.
- Register a paired development-only script-versus-media comparison with visible cohorts, denominators,
  source hashes and limits on interpreting the difference.

**Prerequisite:** no implementation until all three founders agree to the rule-3 interpretation and the
agreement is recorded in the decision log. The user confirmed all-founder agreement on 3 Nov 2026;
the interpretation is now recorded in `docs/notes/decisions.md` and rule 3.

Non-goals: changing the judge or adopted media prompts, tuning from held-out data, a final test run,
automatically approving scripts, editing scripts with the media fix loop, document/PDF import, markdown
rendering, remote asset fetching, deployment or claiming measured gains before a registered comparison.

## Capabilities

### New Capabilities

- `script-screening`: bounded script ingestion, grounded script-line evidence, shared screening and
  customer-facing delivery across CLI, API, web and agent tools.
- `script-media-evaluation`: reproducible paired development comparisons that preserve split boundaries
  and distinguish observed input-mode differences from proven perception losses.

### Modified Capabilities

None. The existing main spec covers optional development tooling, not these runtime behaviours.

## Impact

Schema and generated web contracts, ingestion, claims evidence preparation, pipeline dispatch, API uploads
and preview/retention, reports, tool descriptions and evidence formatting, React input/evidence views,
synthetic replay/browser fixtures and evaluation tooling. Update the product rule and decision record only
after founder agreement; document the input contract and verification in the existing owning documents.
No new external provider or runtime framework is required.
