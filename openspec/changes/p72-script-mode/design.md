# Design

## Context

See [proposal.md](proposal.md) and historical issue #84 from the source project.
This design is based on merged dev `ced06b7`, not the former P43 branch.

Current `Ad` requires image dimensions, and extraction reads either a video or `frames[0]`. The pipeline
always starts three perception tasks. The upload API accepts image/video MIME types and probes media
with FFmpeg. The report, tool formatter and React evidence view expect times, crops or a media player.
A script feature therefore needs an explicit input mode across those boundaries, not renamed transcript
segments with artificial zero timestamps.

The user confirmed the issue's all-founder rule-3 agreement on 3 Nov 2026; the decision is recorded in
the product rules and decision log. The agreed reading is: for a supplied script,
each flag cites its existing policy sources and shows its quoted physical script line and number; the
existing media evidence requirement is unchanged.

## Goals / Non-Goals

Goals: make source-line grounding enforceable, preserve media compatibility, use the common checker and
retention paths, and establish explicit tests for every input/output surface.

Non-goals are in the proposal. In particular, media rendering, fix-loop regeneration, prompt retuning,
deployment and the held-out test are not part of this change. Script mode cannot evaluate pictures that
have not been produced or certify the final edit.

## Decisions

### 1. First-class script input and evidence

Add `Ad.media = "script"`. Make width and height optional at the field level, with validation requiring
positive dimensions for existing media and requiring absent dimensions, duration and fps for scripts.
Do not insert a blank image to satisfy existing consumers.

Store nonblank `ScriptLine` records containing the original positive physical line number, exact raw text
and channel (`voiceover`, `super` or `plain`). Preserve blank-line gaps and line numbers across LF/CRLF;
accept an optional UTF-8 BOM. Recognise case-insensitive leading `VO:`/`SUPER:` hints without changing the
quoted raw text. Markdown is literal: do not render, strip or fetch it. A deterministic parser rejects
whitespace-only content, invalid UTF-8 and binary control content before inference.

Add a discriminated script evidence kind containing line number and exact text. `Screening` holds the
source-line collection and checks evidence against it. A script result cannot carry media evidence, and a
media result cannot carry script evidence or script source lines. A joined claim cites every contributing
line. This makes fabricated citations fail at the same validation boundary as missing media evidence.

Bump the default schema to 3 and regenerate both web contracts. Continue accepting v1/v2 media results,
but reject script-specific fields labelled with an older schema version. Keep v2 vote and sample semantics.
Do not rewrite old saved results, replay records or registered metrics to simulate a migration.

### 2. One parser and pipeline, without perception calls

Extend ingestion dispatch for local `.txt`/`.md` files; keep the original bytes and parsed material inside
the existing ingest/upload boundary, keyed by content hash. Scripts have no audio, video, frames or
keyframes. Use shared script limits across entry points; proposed defaults are 64 KiB and 1,000 physical
lines, with server configuration allowed to lower them.

In `pipeline.gather`, script input creates skipped perception-stage records and passes script lines to
the existing extraction machinery. Extend evidence mapping/listing and use a text-only Spark request,
with a script-specific context/version tag to avoid colliding with cached media requests. Keep the adopted
media prompt bytes and existing media request preparation unchanged. Reuse claim parsing, deduplication,
shortlisting, source validation, voting and the same policy checker rather than a second script checker.
Zero extracted claims still require a completed check record; extraction/check failure remains incomplete.

### 3. Retention and delivery are extensions of existing surfaces

CLI path dispatch and `screen_ad.target` accept script paths and use `screen_target`/`pipeline.screen`.
Guard report/crop preparation against `frames[0]` for scripts; update tool evidence formatting and its
description so a script line is never reported as a timestamp.

Extend the existing upload endpoint with `text/plain` and `text/markdown`. Validate scripts before queuing
a screening instead of sending them to FFmpeg. Preserve opaque IDs, the retention journal, public quotas,
worker admission and per-upload client/cache storage. Errors identify the failure category without
echoing text. Serving a script must use a safe text MIME type and existing expiry checks, not executable HTML.

The web file picker accepts scripts; the workspace displays a scrollable numbered text view and moves to
a cited line when a flag is selected. Render source text through normal escaped text nodes. Report the
script-only limitation in the result headline and script workspace, including for zero-flag results.
Keep every register suggestion exact and provenance intact. Hide media controls and media fix actions for
scripts; reject direct media-fix requests for a script with an explicit unsupported-operation error.

### 4. Paired development measurement without changing the test

Validate a retained, non-void v2 development media baseline and its original cohort before labels or
clients. Build ruling scripts from shot-list voiceover and on-screen lines; never include image prompts
or assessment material. Build team scripts from authored ad copy, excluding label annotations.

Record source/copy hashes and a deterministic line mapping. Run the same checker configuration and voting
settings and register a separate script run and comparison linked to the media baseline. Report the same
items and explicit masks: common textual claims for the paired recall, all script claims separately and
negative-ad false alarms on the matched negative cohort. Missing baseline material is a blocker, not a
reason to regenerate historical model answers or silently select easier ads. The comparison changes input
modality and extraction presentation as well as removing perception, so its gap is not a pure causal
estimate of perception loss. No new measurement exists yet.

## Risks / Trade-offs

- Schema changes reach generated types and old fixtures -> validate historical v1/v2 reads, reject cross-mode
  evidence and build the generated contracts before UI tests.
- Untrusted copy can resemble instructions or markup -> keep it in a delimited evidence payload, restrict
  citations to supplied line IDs, escape all display text and test hostile synthetic input.
- A clean script could be mistaken for a cleared final ad -> retain screening language and an explicit
  finished-ad-check notice in JSON/headline, web, report and tool responses.
- Script lengths affect latency and voting cost -> enforce bounded script inputs and existing public quotas;
  do not introduce background paid calls as part of ingestion or validation.
- Scripts can omit visual or editing context -> state the limit and keep the finished-ad workflow intact.
- The retained dev bundles and original reconstruction assets are absent locally -> offline contract and
  synthetic integration work can be verified, but issue completion still needs a registered paired run.

## Migration Plan

Integration review: P72 and dev independently used schema v3 for different changes.
The combined writer uses v4. Historical v1/v2/v3 media readings retain dimensions
and their version. A saved P72-v3 script is normalised to v4 only in memory during
validation, preserving its evidence and leaving the original file untouched.

Record the agreed rule interpretation first. Implement and test schema/ingestion/pipeline, then API/tool
delivery, report and web support, then synthetic replay/browser integration and documentation. Keep all
tasks incomplete until verified. Finish the dev comparison only with retained inputs and authorised live
calls. P72 remains open until its three issue acceptance criteria are met.

Deploy or publish only on an explicit request. A rollback must not delete v3/v4 script results or relabel them
as v2 media; retain them for the normal expiry window and restore compatible readers before exposing them.
