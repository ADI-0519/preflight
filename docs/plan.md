# PreFlight: build plan

*Drafted 27 October 2026 for the three founders. Every task below is a GitHub issue on the PreFlight project board; this file explains why the tasks are shaped as they are. Decisions marked **open** need a founder's call before the task that depends on them starts.*

## What we are building

PreFlight screens a health or supplement ad before it goes live and shows, for every claim it flags, the evidence on screen or in the voiceover, the rule or register entry the claim conflicts with, and the register's authorised wording where one exists. The hackathon entry has to prove two things in a 3-minute video. First, that PreFlight reaches the ASA's own verdict blind on ads the regulator has already ruled on, reported as breaches caught and false alarms raised on a frozen test split. Second, that an agent can take a fresh draft ad, swap each flagged claim for the register's wording, re-check it until nothing is flagged, and hand it to a person to approve.

Everything in this plan serves those two scenes. Features that neither scene shows (accounts, multi-brand dashboards, a hosted deployment, EU rules) are out of scope until after 4 November.

## Dates that bound the plan

| When (GMT) | What |
|---|---|
| Tue 27 Oct, end of day | Gate checks: Official Rules read logged in; 20-ruling rebuildability sample; Model API smoke test |
| Thu 29 Oct | Register, rulings corpus and split v1 frozen; first ad through transcription and SAM |
| Sat 31 Oct | First end-to-end screening; first blind recall and false-alarm numbers on the dev split |
| Mon 2 Nov | Final run on the test split; agent loop and web page working |
| Tue 3 Nov | Video cut; repo public and checked logged out |
| Thu 5 Nov, 02:00 GMT | Submission deadline (4 Nov, 9:00 PM ET; US clocks change on 1 Nov). Plan to submit by 21:00 GMT on 4 Nov |

The critical path runs through the evaluation: rulings corpus (P13) → split v1 (P14) → reconstructions (P15) → evaluation harness (P31) → final run (P33) → demo assets (P53) → video (P54). A day lost anywhere on that chain is a day lost from the submission. The agent loop and the web page run in parallel with it and can absorb slippage by cutting scope.

## Architecture

### Data flow

```
ad file (video | image | page screenshot)
  │
  ├─ ingest ─────────── ffmpeg: audio track, frames at a fixed rate, change-detected keyframes
  │
  ├─ transcribe ─────── Muse Voice Transcribe → segments with turn timestamps (no word timestamps; P24 decides how to refine)
  ├─ read on-screen ─── Muse Spark on the video → on-screen text with start and end times
  ├─ find regions ───── SAM 3.1, shape and object prompts ("label", "bottle", "black rectangle") → tracks in one call → crops
  │
  ├─ extract claims ─── Muse Spark, structured output → claims (explicit and implied), each tied to evidence
  │
  ├─ check ──────────── register shortlist (substance match) + CAP s.15 rules + precedent rulings (BM25, held-back split excluded)
  │                     → Muse Spark judge, structured output → flags with sources and evidence
  │                     → suggested wording looked up from the register entry, never generated
  │
  └─ report ─────────── Screening (JSON) → CLI, API and web page render the same object
                         clean result: "no issues found against <register, CAP Code and rulings snapshots, dated>"

agent loop (fix):  screening → replace flagged claim text with register wording → regenerate still (Muse Image) if the claim was in an image
                   → re-screen → repeat until clean or N rounds → awaiting human approval → audit log
```

### Modules

The package is `preflight` (src layout). Stages exchange schema objects only, so any stage can be rerun from saved inputs and tested with recorded model responses.

| Module | Responsibility | Talks to a model? |
|---|---|---|
| `preflight.schema` | Pydantic models: `Ad`, `Segment`, `Track`, `Region`, `Claim`, `Evidence`, `SourceRef`, `Flag`, `SuggestedWording`, `Screening` | no |
| `preflight.models` | One thin client per Meta model (Spark, Voice Transcribe, SAM 3.1, Image) plus Glimmer; content-hash cache; record and replay for tests | the only module that does |
| `preflight.sources` | Register loader, CAP rule pack, rulings corpus and scraper, snapshot versions | no |
| `preflight.ingest` | Video, image and page-screenshot input; frame sampling | no |
| `preflight.evidence` | Transcription and region stages → segments, tracks, crops, on-screen text | via `models` |
| `preflight.claims` | Claim extraction prompt and parser | via `models` |
| `preflight.check` | Register shortlist, precedent retrieval, judge prompt, flag assembly | via `models` |
| `preflight.agent` | Fix loop, audit log, tool interface | via `models` |
| `preflight.eval` | Split manifests, reconstructions, scoring, run registry, baseline | via `models` (reconstruction only) |
| `preflight.api` | FastAPI app: upload, screen, progress over SSE, fix, approve, retention | no |
| `web/` | One static page: player, claim timeline, crops, flags, approval; demo mode with ruling reveal and scoreboard | no |

Prompts live in `prompts/` as versioned text files; the prompt version is part of the cache key and of every run record.

### Output schema (contract for P21)

A `Screening` records the ad's content hash, the snapshot versions of the register, CAP rule pack and rulings index, the model and prompt versions, the claims, the flags and the fixed notice text. A `Flag` must carry at least one `SourceRef` (register entry ID, CAP rule number, or ruling ID and date) and at least one `Evidence` (transcript segment with start and end time, or region with frame time and crop), and the schema rejects a flag without both (rule 3). `SuggestedWording` holds a register ID and that entry's wording copied from the snapshot; it has no free-text constructor (rule 2). There is no "compliant" or "approved" state anywhere in the schema; approval is a separate human action recorded in the audit log (rule 4).

### How each Meta model is used

Checked by calling each model in P03; details in `docs/notes/meta-model-api-findings.md`.

| Job | Model | Why this one | Price (published, confirmed in P03) |
|---|---|---|---|
| Voiceover to text with timestamps | Muse Voice Transcribe (`muse-voice-transcribe-1.0`) | Spark 1.3 mistimes speech in video; this model gives an accurate transcript under music, but turn-level timestamps only | $0.18 per hour |
| Read on-screen text with its timing | Muse Spark 1.3 on the video | Read every overlay and the small print with times correct to the second | $1.25 in / $4.25 out per million tokens |
| Find claim-bearing visuals and track them | SAM 3.1 (`sam-3.1`) | One call tracks objects with stable IDs across a whole clip: pack shots, labels, before/after shots, boxed captions. It does not find text as such, so prompts name objects and shapes | $0.20 per 1,000 video frames (every decoded frame, minimum 50), $2.50 per 1,000 images |
| Extract claims, judge them, drive the agent | Muse Spark 1.3, Standard mode (`muse-spark-1.3`, never `-contributor`) | Structured output with strict JSON schema, tool calls, 1M context; Standard mode does not train on inputs | as above; reasoning effort set per stage |
| Rebuild ruled ads; regenerate a fixed still | Muse Image (`muse-image-1.0`) | Reconstructions for the benchmark and the fix loop; no block on supplement health claims | $0.01 per image |
| First-pass triage that can run on an agency's own hardware | Muse Glimmer (open weights, via partner inference) | Confidentiality story and the open-weights bonus; optional; not on Model API | partner credits |

Measured in P03: a 30-second 720p ad costs about $0.15 in SAM at 25 fps (about $0.03 if re-encoded at 5 fps before upload) and about $0.02–0.05 in Spark at low or medium reasoning effort, so a 60-item benchmark run stays under $15.

### Stack (recommended; founders to confirm in P05)

- **Python 3.12 managed by uv.** The machine has 3.14, but nothing here needs it and 3.12 has the widest wheel support. Pydantic v2 for the schema, the OpenAI Python SDK pointed at `https://api.meta.ai/v1` for the Meta models (the docs say the API is OpenAI-compatible; P03 confirms which endpoints are), httpx, ffmpeg through subprocess, `rank-bm25` for precedent retrieval, FastAPI with server-sent events, pytest with recorded responses, ruff, GitHub Actions.
- **Web page:** one HTML file with plain JavaScript and CSS. No build step.
- **Storage:** files on disk. Screenings as JSON under a runs directory, evaluation runs registered in `results/runs.csv`, uploads under `data/raw/` with a retention log. No database until something needs one.
- **No hosted deployment** before submission. The video and a public repo are what the rules ask for; a deployment is a post-hackathon task.
- **Open decision (P05): voiceover for reconstructions.** Meta offers no text-to-speech. Options: (a) a local open-source TTS (e.g. Piper) used only by the fixture builder, so the screening path stays entirely on Meta models; (b) reconstructions without voiceover, carrying claims in captions and stills only. Recommendation: (a), because the voiceover is where half the claims in real ads sit, and a benchmark without it would not exercise Voice Transcribe.

## Evaluation protocol (contract for P14 and P31)

1. **Items.** Positives are recent ASA rulings on food supplement health claims, chosen by date (most recent first) and capped at two per advertiser. Negatives are not-upheld rulings in the same topics, ads the team writes using only verbatim register wording, and partners' approved ads where consent exists. Each item carries a ground-truth list of breaching claims (empty for negatives) written from the ruling's assessment by one founder and checked by another.
2. **Split.** `eval/splits/v1.yaml` lists item IDs in `dev` and `test`. Prompts and thresholds are tuned on `dev` only. `test` runs once per final configuration. Changing either list means `v2`, never an edit.
3. **Reconstructions.** Built only from the ruling's "Ad description" section. The builder's input type holds that section and nothing else, and a test enforces it. Every reconstruction is labelled "AI reconstruction from ASA ruling text" in its metadata and on screen.
4. **Leakage.** The precedent index, few-shot examples and prompts are built with every `test` and `dev` ruling excluded. The index builder reads the split manifest and refuses to build if an excluded ID is present.
5. **Metrics.** Claim-level recall (breaching claims flagged with a matching reason), ad-level recall (ads with at least one correct flag), and false-alarm rate (flags per negative ad, and the share of negative ads with any flag). Reported as counts with their denominators ("caught 27 of 30 breaching ads; flagged 2 of 30 compliant ads"), never as one accuracy figure, with bootstrap intervals over items once the counts allow.
6. **Baseline.** A keyword and register-lookup screen with no model calls, on the same split, so the video can say what the models add.
7. **Records.** Each run writes per-item rows (CSV) and registers itself in `results/runs.csv` with the split version, model and prompt versions, snapshot versions and git SHA. Numbers in the README, page or video come only from registered runs.

## Product rules

The ten rules in `docs/product-rules.md` govern every task. Rules 8–10 were added for this plan, because the replay demo creates three new ways to go wrong: leaking the ruling's answer into a reconstruction, publishing a verdict on an ad the ASA has not ruled on, and sending partner material to a mode that trains on it. P05 confirms all ten.

## Lanes

Work is split into three lanes so that each founder owns a chain of dependencies:

| Lane | Owns |
|---|---|
| A: data and evaluation | sources, rulings corpus, split, reconstructions, harness, baseline, final numbers |
| B: media and model pipeline | Model API checks, scaffold, model clients, ingest, transcription, regions, claim extraction, Glimmer |
| C: checker, agent and demo | schema, checker, report and CLI, agent loop, tool interface, API, web page, demo assets, README |

Tasks in lane `all` need every founder: reading logged-in pages, contacting partners, recording the video and submitting.

## Tasks

| ID | Task | Lane | Depends on | Due |
|---|---|---|---|---|---|
| P01 | Read the Official Rules logged in and record what they fix | all | – | 27 Oct |
| P02 | Sample 20 rulings for rebuildability and record asa.org.uk terms | A | – | 27 Oct |
| P03 | Smoke-test the Meta Model API and record what each model does | B | – | 27 Oct |
| P04 | Scaffold the Python package, lint, tests and CI | B | – | 27 Oct |
| P05 | Founders' decisions: rules, stack, topics, lanes, go/no-go | all | P01, P02, P03 | 27 Oct |
| P06 | Design-partner outreach to agencies | all | – | 2 Nov |
| P07 | Verify the hook facts from primary sources | A | – | 28 Oct |
| P11 | Ingest the GB register into versioned snapshots | A | P04 | 28 Oct |
| P12 | Write the CAP Code section 15 rule pack | A | P04 | 28 Oct |
| P13 | Build the ASA rulings corpus | A | P02, P04 | 29 Oct |
| P14 | Freeze evaluation split v1 with ground truth | A | P11, P13 | 29 Oct |
| P15 | Build reconstructions from ad descriptions | A | P03, P14 | 30 Oct |
| P21 | Define the output schema v1 | C | P04 | 28 Oct |
| P22 | Write the model clients with caching and replay | B | P03, P04 | 28 Oct |
| P23 | Ingest video, images and page screenshots | B | P04 | 29 Oct |
| P24 | Transcription stage | B | P21, P22, P23 | 29 Oct |
| P25 | On-screen evidence stage with SAM 3.1 | B | P21, P22, P23 | 30 Oct |
| P26 | Claim extraction prompt and parser | B | P24, P25 | 30 Oct |
| P27 | Checker: register, CAP rules, precedent, judge | C | P11, P12, P13, P14, P21, P26 | 31 Oct |
| P28 | Report rendering and the `preflight screen` CLI | C | P27 | 31 Oct |
| P31 | Evaluation harness and run registry | A | P14, P15, P28 | 31 Oct |
| P32 | Keyword and register-lookup baseline | A | P11, P31 | 1 Nov |
| P33 | Error analysis on dev, then the final test run | A | P31 | 2 Nov |
| P41 | Agent fix loop with audit log | C | P22, P28 | 1 Nov |
| P42 | Expose screen and fix as a tool agents can call | C | P41 | 2 Nov |
| P43 | Glimmer confidential triage (optional, cut first) | B | P22, P28 | 1 Nov |
| P51 | FastAPI service with progress events and retention | C | P28 | 1 Nov |
| P52 | Web page with demo mode | C | P51 | 2 Nov |
| P53 | Demo assets: replay rulings and a fresh ad | C | P33, P41, P52 | 3 Nov |
| P54 | Script, record and cut the 3-minute video | all | P53 | 3 Nov |
| P55 | README, benchmark write-up, repo public | C | P33 | 3 Nov |
| P56 | Submit with every teammate | all | P54, P55 | 4 Nov |

**Cut order if behind:** P43 (Glimmer), then P42 (tool interface), then the image-regeneration step of P41, then product-page input in P23. P14, P15, P31, P33 and the register-wording rewrite in P41 are never cut.

## Open decisions

| Decision | Recommendation | Decided in |
|---|---|---|
| Keep, reframe or switch | Reframe; switch to DampTrace only if a P01 or P02 gate fails | P05 |
| Confirm product rules 1–10 | Confirm as drafted | P05 |
| Stack | As above | P05 |
| Two topics built fully | Mushroom and magnesium supplements (both inside the register and CAP s.15), ADHD-claim supplements as the hook | P05 |
| Reconstruction voiceover | Local TTS in the fixture builder only | P05 |
| Lane owners | One founder per lane | P05 |
| Repo visibility | Private until P55, then public | P55 |
