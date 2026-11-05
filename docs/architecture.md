# Architecture

PreFlight is a Python package, `preflight`, of pipeline stages that pass typed objects to one another. A screening takes one ad and returns one `Screening` object, which the HTML report, the API, the web page and the agent tools all render. The stages call Meta's models through the OpenAI-compatible Model API in Standard mode, which does not train on its inputs.

## Data flow

```
ad (video | image | carousel | page URL | script)
  │
  ├─ ingest ─────────── ffmpeg: audio track, frames at a fixed rate, keyframes at shot cuts;
  │                     carousel cards joined into one silent slideshow; a URL captured as a page screenshot
  │
  ├─ transcribe ─────── Muse Voice Transcribe → turns → local MMS forced aligner → word timings
  │                     (a turn's own start and end are kept where alignment fails or scores low)
  ├─ read on-screen ─── Muse Spark on the video → on-screen text with start and end times
  ├─ find regions ───── SAM 3.1 with object and shape prompts → tracked boxes → crops
  │
  ├─ extract claims ─── Muse Spark, strict JSON schema → claims, stated or implied, each tied to its evidence
  │
  ├─ check ──────────── register entries shortlisted by substance + CAP Code rule pack
  │                     + similar past rulings (BM25 over the rulings corpus, held-back rulings excluded)
  │                     → Muse Spark judge, three samples; a claim is flagged when two agree
  │                     → suggested wording looked up in the register entry, never generated
  │
  └─ report ─────────── Screening (JSON) → view (lines a reviewer reads, ranked by risk) → HTML, API, web, tools

fix loop:  screening → flagged lines replaced with register wording → Muse Image removes a claim from a still
           when a picture holds it → screen again → repeat until nothing is flagged or a person must take over
           → awaiting approval → a person records approval → audit log
```

A script (`.txt` or `.md`) skips ingest, transcription and the on-screen stages. Its lines go straight to claim extraction and the check, and each flag quotes its numbered source line as evidence. A script screening covers the words only, so the finished ad needs its own screening.

## What the schema guarantees

The output schema in `preflight.schema` is the single contract. The pipeline, the API, the front end and the evaluation harness all read it, and `web/schema.json` is generated from it (`uv run python -m preflight.schema`; a test fails if the generated file is stale). The current version is 4. Older screenings stay readable.

The schema enforces these properties by type:

- A `Flag` needs at least one source and at least one piece of evidence, or it cannot be built. A source is a register entry ID, a CAP Code rule number, an entry on the DHSC on-hold list, or an ASA ruling ID with its date. Evidence is a transcript segment with start and end time, an on-screen region with its frame time and crop, on-screen text with its times, or a quoted script line with its line number.
- `SuggestedWording` holds a register ID and that entry's text copied from the snapshot. It has no constructor that takes free text.
- There is no "compliant", "passed" or "approved" state. The clean headline is a fixed notice naming the dated snapshots used. Approval is a separate action by a person, written to an append-only audit log.
- A stage that fails is recorded with its error. If any stage fails, or the check does not finish, the headline reads "Incomplete" and never "No issues found".

Types cannot prove that a register ID exists or that copied wording matches its entry. `verify_sources(screening)` checks every register, on-hold, CAP and ruling reference, and every suggested wording, against the snapshots the screening names. The check runs it on every screening it returns, and the API and the fix loop run it again on every screening they accept.

Objects are immutable, and each stage records its model, prompt version, reasoning effort, number of judge samples and status.

## One pipeline

`preflight.pipeline` holds the only screening function. The CLI (`preflight screen`), the API, the agent tools (`screen_ad`, `fix_ad`) and the evaluation harness all call it, so a figure measured by the harness describes the same code a user runs. The one difference is the precedent index. Evaluation gives each test item its own pool of earlier rulings ([evaluation.md](evaluation.md#leakage)), while the CLI, the API and the tools leave out every ruling in the evaluation split, so a demo reconstruction never cites its own ruling.

## Sources and snapshots

Every source is a dated snapshot in `data/snapshots/`, and every screening records which one it used.

| Source | Snapshot | What it holds |
|---|---|---|
| GB nutrition and health claims register | `register-2026-05-19.jsonl` 297 authorised and 2,082 non-authorised entries, each with its wording and conditions of use; Open Government Licence |
| DHSC on-hold list | `on-hold-2021-01-12.jsonl` | Botanical claims that may still be used in Great Britain while they await a decision; cited as context, never offered as wording |
| CAP Code rule pack | `cap-2026-11-02.yaml` | Rule numbers with short summaries written for this project; the Code's text is not copied |
| ASA rulings index | `rulings-2026-11-02.jsonl` | Metadata only: ID, date, advertiser, outcome, rules cited and URL |

The ruling pages themselves are cached locally under `data/raw/rulings/` and never committed. What each source's terms allow is set out in [source-terms.md](source-terms.md).

## Reproducibility

Prompts are versioned text files in `prompts/`. `preflight.models` is the only module that calls a model, and it caches each answer under a hash of the request, which includes the prompt version. With `--replay`, every model call is answered from the cache and a missing answer fails the run, so a recorded screening reruns exactly with no API key. Tests use recorded answers in `tests/fixtures/models/` and never call the API unless they are marked `live`.

Scored evaluation runs are registered in `results/runs.csv` with the split version, model and prompt versions, snapshot versions, git commit and cost ([evaluation.md](evaluation.md#records)).

## Modules

| Module | Responsibility | Calls a model |
|---|---|---|
| `preflight.schema` | Pydantic models for ads, segments, tracks, regions, claims, evidence, sources, flags, suggested wording and screenings; `verify_sources` | no |
| `preflight.models` | One thin client per model, the content-hash cache, record and replay | the only module that does |
| `preflight.sources` | Register and on-hold loaders, the CAP rule pack, the rulings corpus, snapshot versions | no |
| `preflight.ingest` | Video, image, carousel, page and script input; frame sampling and keyframes | no |
| `preflight.evidence` | Transcription, word alignment, on-screen text, regions and crops | through `models` |
| `preflight.claims` | Claim extraction prompt and parser | through `models` |
| `preflight.check` | Register shortlist, precedent retrieval, the judge and its vote, flag assembly | through `models` |
| `preflight.pipeline` | The screening function: runs the stages in order and records any failure | through `models` |
| `preflight.view` | Folds a flagged phrase under the longer flagged line that contains it, ranks lines high, medium or low risk, lists the register entries for each flagged substance | no |
| `preflight.report` | Renders the view as one self-contained HTML page | no |
| `preflight.agent` | Fix loop, drafts, audit log, approval, the `screen_ad` and `fix_ad` tools and their MCP server | through `models` |
| `preflight.eval` | Split manifests, reconstructions, scoring, the keyword baseline, stress sets and the run registry | reconstruction only |
| `preflight.api` | FastAPI service: uploads, jobs, progress over server-sent events, fixes, approvals, retention, sign-in, public-mode limits | no |
| `web/` | React and TypeScript workspace built by Vite and served by FastAPI | no |

Risk tiers come from the rules on a line. A line citing CAP Code section 12 or rules 15.6.x (medicinal and disease claims) is high, other rules in sections 15 and 3 are medium, and the rest are low.

## Models

Prices are the published ones, read on 31 October 2026.

| Job | Model | Why | Price |
|---|---|---|---|
| Voiceover to text | Muse Voice Transcribe (`muse-voice-transcribe-1.0`) | Accurate under music; returns turn timings only, so words are aligned locally | $0.18 per hour |
| On-screen text with its timing | Muse Spark 1.3 on the video | Reads overlays and small print with times to the second | $1.25 in, $4.25 out per million tokens |
| Claim-bearing visuals | SAM 3.1 (`sam-3.1`) | Tracks objects with stable IDs across a clip in one call. It does not find text as such, so the prompts name shapes and objects: caption boxes, labels, bottles | $0.20 per 1,000 video frames, $2.50 per 1,000 images |
| Claims, judging, the agent | Muse Spark 1.3, Standard mode (`muse-spark-1.3`) | Strict JSON-schema output and tool calls; Standard mode does not train on inputs | as above |
| Fixed stills; benchmark reconstructions | Muse Image (`muse-image-1.0`) | Edits a still to remove a claim; draws pictures for rebuilt ads | $0.01 per image |

The registered test run cost $24.15 for 79 ads, about $0.31 an ad.

## Stack

- Python 3.12 managed by uv; Pydantic v2; the OpenAI Python SDK pointed at `https://api.meta.ai/v1`; httpx; ffmpeg through subprocess; `rank-bm25` for precedent retrieval.
- Optional extras: `align` (PyTorch and torchaudio for the MMS aligner), `page` (Playwright for page capture), `render` (Piper text-to-speech for rendering drafts and reconstructions), `mcp` (the MCP server), `api` (FastAPI, Uvicorn, PyJWT).
- FastAPI with server-sent events serves the API and the built front end from one process. The front end is React with TypeScript, built by Vite in `web/`; no key or model call reaches the browser.
- Storage is files on disk: screenings as JSON, uploads under a retention log, evaluation runs in `results/`. There is no database.
- CI on GitHub Actions runs ruff and the offline tests, then the front end's type check, build, formatting check and unit tests, and a browser workflow over real HTTP with recorded model answers and the network blocked.
- Deployment is one Cloud Run container ([deploy.md](deploy.md)).
