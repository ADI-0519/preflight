## Context

P51 exposes jobs and final screenings but not source playback, crop retrieval or
saved fix rounds. Dev P42 and later review fixes are already integrated in HEAD.
The current checkout has no results/final.md selection or final P53 demo assets.

## Goals / Non-Goals

Deliver the local browser workflow in issue #28 with evidence and honest provenance.
No model prompts, frozen splits, registered metrics, authentication, publishing or
deployment changes. Preserve separate human and platform decisions.

## Decisions

- React with plain local state, TypeScript types generated from web/schema.json,
  Vite static output and same-origin API requests. No component kit or state library.
- Persist job IDs in the URL only. SSE owns progress; fetching a completed result
  and fetching status once on reload are not polling. Close streams on cleanup.
- Presentation derives source descriptions from repository snapshots after
  verify_sources. Crops use exact track/region indices and source-confined paths.
- Media reads copy bytes under the retention lock and support single byte ranges.
  Fix history verifies each recorded Screening and returns no filesystem paths.
- The page accepts one editable scene for a fresh fix. P41 renders and re-screens;
  the UI does not pretend an uploaded video is already an editable source project.
- An explicit name, confirmation and button press record human review. The server
  remains authoritative for completion, remaining flags and repeated decisions.
- Operator-owned demo manifest points only inside its ignored root. Outcomes come
  from the screening's repository ruling snapshot, not manifest-authored policy.
- A single run_id line in results/final.md selects registry rows. Only registered
  test screening rates with clean revisions and valid denominators are displayed.
  Development numbers, replay counts, cost and timing never become final percentages.

## Risks / Trade-offs

Source cache restoration and live model availability are independent of browser
contracts. Synthetic tests label recordings and do not prove model accuracy. P53
asset selection and P33 final metrics remain external acceptance dependencies.
The local prototype still has no authentication or tenant isolation. Upload memory
is bounded by the existing 100 MiB cap; public serving needs separate work.

## Migration Plan

### Approved presentation follow-up

The 1 November design review replaces the editorial header with a compact
media-first workspace. Loaded results use evidence, editable-draft and saved-round
views. A time axis supplements the complete accessible claim list; all claims and
flags remain available. Saved rounds can be selected side by side with exact
changed caption lines highlighted. Charcoal and light appearances use local CSS
tokens. The full notice stays visible in the application shell. No API, policy,
model, evaluation or decision-eligibility change is part of this pass.

Install the locked web dependencies, build before starting Uvicorn and visit `/`.
Existing API clients remain compatible. Without a build, `/` returns a clear 503.
Configure final assets and run selection when their owning phases are complete.
