# PreFlight

PreFlight reads a health or food-supplement ad before it goes out and marks the claims that UK advertising rules are likely to object to. Give it a video, an image, a screenshot of a product page or the script. It lists every claim the ad makes, including the ones a picture makes, such as a before-and-after shot, and checks each against the GB nutrition and health claims register, the CAP Code and the ASA's past rulings. Each flag shows where the claim sits in the ad (a transcript timestamp, a region of a frame, or a numbered script line) and the rule or ruling it conflicts with. When the register authorises a claim for the same substance, PreFlight quotes that wording exactly, with its register ID, as the replacement.

PreFlight screens ads. It gives no legal advice and never approves an ad: a clean result reads "no issues found against" the dated versions of the sources it used, and a person decides whether the ad runs. The ten rules the product keeps to are in [docs/product-rules.md](docs/product-rules.md).

It runs on Meta's models: Muse Spark reads the ad and judges the claims, SAM 3.1 finds regions on screen, Muse Voice Transcribe transcribes the voiceover and Muse Image edits stills in the fix loop and rebuilds ruled ads for testing.

A hosted copy runs at <https://preflight-ai.web.app>. Sign-in is by an emailed code and limited to an allowlist, since every screening spends model credit. Uploads are deleted after 24 hours.

## Results

Testing needs ads whose breaches are already known. The ASA publishes a ruling on every ad it investigates, naming the claims that broke each rule, but the ruling pages carry no image or video. Each test ad is therefore rebuilt from the ruling's own description of it, and PreFlight screens the rebuild without seeing the ruling. Rulings held back for testing never reach a prompt, an example or the precedent index. The test part of split v2 was frozen and then run once. It holds 79 ads:

- 49 rebuilt from upheld ASA rulings;
- 10 near-miss ads, each a clean ad with one breaching line added;
- 20 clean ads that use only authorised register wording.

PreFlight is compared with a keyword baseline that uses no models. The baseline flags a sentence that names a register substance beside a benefit word ("supports", "immune") without the authorised wording, and a sentence that names a disease, symptom or cure word. It reads each ad's text as written, while PreFlight has to read the same text off the rendered video through transcription and on-screen reading, so the comparison favours the baseline. The full method is in [docs/evaluation.md](docs/evaluation.md#baseline).

| Measure (split v2 test) | PreFlight | Keyword baseline |
|---|---|---|
| Ads with a breach that were flagged | 54 / 59 (92%) [81, 97] | 28 / 59 (47%) [34, 61] |
| Breaching claims caught with a matching rule | 334 / 530 (63%) [54, 72] | 47 / 530 (9%) [5, 13] |
| Near-miss lines caught | 10 / 10 [69, 100] | 7 / 10 [35, 93] |
| Clean lines flagged in near-miss ads | 0 / 77 | 0 / 77 |
| Clean ads flagged | 1 / 20 (5%) [0, 25] | 0 / 20 [0, 17] |
| Cited rules that match a rule the ASA cited | 868 / 1276 (68%) [59, 78] | 106 / 124 (85%) [72, 96] |
| Flagged lines that match no ruled claim, per breaching ad | 6.2 | 0.6 |
| Model cost | $24.15 for 79 ads | none |

Brackets are 95% intervals in percent: exact for counts of ads, and bootstrapped over ads for counts of claims, lines and rules. Runs `screen-20261104T052428` and `baseline-20261104T052523`; the table is generated into [results/final.md](results/final.md) from [results/runs.csv](results/runs.csv), and the web page's scoreboard shows the same two runs side by side.

Most of the difference from the baseline is recall. PreFlight caught 63% of breaching claims with a matching rule, the baseline 9%. Keywords find a breach in fewer than half of the ruled ads, and they cannot see a claim an ad makes through a testimonial, a picture or a product presented for a condition.

On false alarms the two are close. PreFlight flagged one of the 20 clean ads, the baseline none, and neither flagged a clean line in the near-miss ads. Where PreFlight is noisier is in the ruled ads themselves, with about six flagged lines per ad that match no claim in the ruling. Not all of these are errors. Of 149 such lines classified by hand from an earlier development run, 45 were real problems the ASA had not taken up (dosing claims for children, testimonials of results, "clinically backed"). The baseline's higher rule precision comes from citing far fewer rules, nearly all from section 15, which almost every ruling names.

The largest known gap is CAP Code section 12, on medicinal claims. It is about 1% of the rules the ASA cited in the development rulings and 26% in the test rulings, which are later and lean on medicinal and anti-ageing claims. Two judge prompts that add section 12 were measured afterwards on rulings outside both parts. Neither became the default: the stronger one cited section 12 on more than half its flags and lowered rule precision. The test figures above come from the prompt that was frozen before the run.

## How it works

```
ad (video | image | carousel | page URL | script)
  │
  ├─ ingest ─────────── ffmpeg: audio track, sampled frames, keyframes at shot cuts;
  │                     carousel cards joined into one slideshow; a URL captured as a page screenshot
  ├─ transcribe ─────── Muse Voice Transcribe → turns → local MMS aligner → word timings
  │                     (turn timing kept where alignment fails)
  ├─ read on-screen ─── Muse Spark on the video → on-screen text with start and end times
  ├─ find regions ───── SAM 3.1 tracks caption boxes, packs and before/after shots → crops
  │
  ├─ extract claims ─── Muse Spark, strict JSON output → every claim, stated or implied, tied to its evidence
  │
  ├─ check ──────────── register entries shortlisted by substance + CAP Code rule pack
  │                     + similar past rulings (BM25, held-back rulings excluded)
  │                     → Muse Spark judge, asked three times; a claim is flagged when two answers agree
  │                     → suggested wording looked up in the register, never generated
  │
  └─ report ─────────── one Screening object → HTML report, API, web page and agent tools
                         flagged lines ranked high, medium or low risk

fix loop:  flagged line → register wording → Muse Image removes the claim from a still if a picture holds it
           → screen again → repeat until nothing is flagged or a person must take over → audit log
```

A script skips the perception stages and goes straight to claim extraction, with each flag quoting its numbered source line.

### What the design guarantees

The output schema is the contract every part reads. A flag cannot be built without both a source (a register entry, a CAP rule number, or a ruling ID and date) and evidence (a transcript time, a frame region or a script line). Suggested wording has no free-text constructor: it can only be an entry copied from the register snapshot. The schema has no "compliant" or "approved" state, and approval is a separate action by a person, written to an audit log. Since types cannot prove that a register ID exists, `verify_sources` checks every reference and every suggested wording against the snapshots the screening names, and it runs on every screening the pipeline returns and the API accepts.

A stage that fails is recorded, never hidden. If any stage or the check did not finish, the headline reads "Incomplete", never "No issues found".

There is one pipeline. The CLI, the API, the agent tools and the evaluation harness all call the same `pipeline.screen`, so the test figures above describe the code the web page runs.

Every run can be reproduced. Each screening records the dated snapshot of the register, the on-hold list, the CAP rule pack and the rulings index it used, and the model, prompt version and reasoning effort of each stage. Prompts are versioned files in `prompts/`, and the prompt version is part of the model cache key. Model answers are cached by content hash, so `--replay` reruns a screening exactly without an API key. Scored runs go into `results/runs.csv` with the commit they ran from.

### Modules

| Module | Does | Calls a model |
|---|---|---|
| `preflight.schema` | Pydantic models for ads, evidence, claims, flags and screenings; `verify_sources` | no |
| `preflight.models` | One thin client per Meta model, the content-hash cache, record and replay | the only module that does |
| `preflight.sources` | Register, on-hold list, CAP rule pack and rulings corpus, each a dated snapshot | no |
| `preflight.ingest` | Video, image, carousel, page and script input; frames and keyframes | no |
| `preflight.evidence` | Transcription, word alignment, on-screen text, regions and crops | through `models` |
| `preflight.claims` | Claim extraction prompt and parser | through `models` |
| `preflight.check` | Register shortlist, precedent retrieval, the judge and its vote, flag assembly | through `models` |
| `preflight.pipeline` | The one screening function, which runs the stages in order and records failures | through `models` |
| `preflight.view`, `preflight.report` | Fold nested flags into reviewable lines, rank them by risk, render the HTML report | no |
| `preflight.agent` | Fix loop, audit log, approval, and `screen_ad` and `fix_ad` as tools and over MCP | through `models` |
| `preflight.eval` | Splits, reconstructions, scoring, the keyword baseline and the run registry | reconstruction only |
| `preflight.api` | FastAPI: uploads, jobs with progress over server-sent events, fixes, approvals, 24-hour retention, sign-in, public-mode limits and spend cap | no |
| `web/` | React and TypeScript workspace: player, claim timeline, evidence crops, sources, register wording, scoreboard | no |

The full architecture, with the models and their prices, is in [docs/architecture.md](docs/architecture.md), and the evaluation method in [docs/evaluation.md](docs/evaluation.md).

## Running it

You need [uv](https://docs.astral.sh/uv/), which installs Python 3.12 if it is missing, and FFmpeg on the PATH.

```
uv sync
cp .env.example .env    # then fill in the values: see "Settings (.env)" below
uv run pytest           # skips tests marked live
uv run ruff check
```

Tests marked `live` call the real Meta Model API and run only with `uv run pytest -m live`.

Screen one ad from the command line:

```
uv run preflight screen ad.mp4
uv run preflight screen card1.png card2.png card3.png    # one carousel, in order
uv run preflight screen script.txt --no-align
```

Each screening writes a JSON file and an HTML report under `data/work/screenings/`. A script is UTF-8 `.txt` or `.md`, up to 64 KiB and 1,000 lines, with optional `VO:` and `SUPER:` prefixes; its flags quote the numbered source line. A script screening covers only the script, so the finished ad still needs screening on its own. The input rules are in [docs/api.md](docs/api.md#script-input).

`preflight screen`, `preflight fix` and `scripts/agent_demo.py` take `--replay`, which answers every model call from the recordings in `data/cache/` and fails the run on a missing one. It needs no `META_API_KEY`. For a synthetic replay with no credentials or network at all:

```powershell
uv run --offline python scripts/verify_screening_replay.py --out data/work/verification/replay-001
```

Use a new output directory each time. This checks the recorded-response contracts and the rendering, not the models' accuracy.

### Web workspace

```powershell
uv sync --locked --extra api --extra page --extra mcp
npm ci --prefix web
npm --prefix web run build
uv run uvicorn preflight.api:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

Open <http://127.0.0.1:8000/>. Live screening also needs the cached ASA ruling pages under `data/raw/rulings/`, which are not in the repo. The page, the API and the deployment are documented in [docs/web.md](docs/web.md), [docs/api.md](docs/api.md) and [docs/deploy.md](docs/deploy.md).

### Settings (.env)

`.env.example` is the template: copy it to `.env`, which git ignores, and fill in the values. Never commit them or paste them into issues, docs or chat. The tests need none of them.

| Variable | Needed for | Where the value comes from |
|---|---|---|
| `META_API_KEY` | Live screening and fixes (not `--replay`, not tests) | Meta Model API account |
| `FIREBASE_PROJECT_ID`, `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `FIREBASE_APP_ID` | Sign-in; leave `FIREBASE_PROJECT_ID` empty to run open locally | Team Firebase project > Project settings > Your apps > Web app |
| `PREFLIGHT_SESSION_SECRET` | Sign-in sessions that survive a restart | Any long random string you generate |
| `PREFLIGHT_ALLOWED_EMAILS` | Limiting who can sign in (emails, or `@domain`) | Set it yourself; required on a deployment |
| `PREFLIGHT_SMTP_HOST`, `PREFLIGHT_SMTP_PORT`, `PREFLIGHT_SMTP_USER`, `PREFLIGHT_SMTP_PASSWORD`, `PREFLIGHT_MAIL_FROM` | Emailing the 6-digit sign-in code when sign-in is on | A mail account; for Gmail, `smtp.gmail.com`, port 587 and an App Password |
| `PREFLIGHT_DEV_CODES` | Local sign-in without email: `1` writes codes to the server log | Set it yourself; never on a deployment |
| `PREFLIGHT_PUBLIC_MODE` | Public demo limits: `on`, or `replay` for preloaded demos only | Set it yourself |
| `BASETEN_API_KEY`, `GLIMMER_MODEL` | A development-only triage experiment on Muse Spark Open, never used in screening | Baseten account |
| `PREFLIGHT_ALLOWED_HOSTS` | A deployment's public host names (local runs need none) | Set by `deploy/cloud-run.sh`; see [docs/deploy.md](docs/deploy.md) |
| `PREFLIGHT_DAILY_CAP_USD` | Public mode's daily model spend cap across all visitors (default 40) | Set by `deploy/cloud-run.sh` (10); see [docs/deploy.md](docs/deploy.md) |

For local work only `META_API_KEY` matters. With the sign-in variables empty, the workspace runs open on localhost.

### As a tool for other agents

PreFlight offers two tools. `screen_ad` screens a video, image or page and returns the flagged lines, each with its CAP rules, sources, evidence and any register wording, plus the register's authorised entries for each flagged substance. `fix_ad` screens a draft and swaps flagged lines for register wording. A draft can be only a script, voiceover and on-screen text, which `fix_ad` renders on a plain card. Neither tool can approve or publish.

To serve them to an MCP client over stdio, install the extras (`uv sync --extra mcp --extra render`) and add this to the client's config, with the path to this repository:

```json
{"command": "uv", "args": ["run", "--directory", "<path to repo>", "--extra", "mcp", "--extra", "render", "preflight", "mcp"]}
```

The tools open any file path or URL the calling agent passes and send the ad to the Meta Model API, so connect them only to agents you trust. Results go under `data/work/agent/`. `scripts/agent_demo.py <draft.yaml>` shows an agent that calls `screen_ad` on a draft before it would publish; it needs the `render` extra.

## Where things are

| Path | What |
|---|---|
| `src/preflight/` | The pipeline stages, CLI, API, agent tools and evaluation harness |
| `web/` | The React and TypeScript workspace, built by Vite and served by FastAPI |
| `data/snapshots/` | Dated snapshots of the register, the on-hold list, the CAP rule pack and the rulings index |
| `eval/` | Split lists, ground truth and near-miss items |
| `results/` | `runs.csv`, the registry of every scored run, and the generated `final.md` |
| [docs/architecture.md](docs/architecture.md) | Data flow, schema guarantees, modules, models and stack |
| [docs/evaluation.md](docs/evaluation.md) | Test items, split, leakage rules, scoring, baseline and run records |
| [docs/product-rules.md](docs/product-rules.md) | The ten rules every output and evaluation follows |
| [docs/api.md](docs/api.md), [docs/web.md](docs/web.md), [docs/deploy.md](docs/deploy.md) | The API, the web workspace and the Cloud Run deployment |
| [docs/source-terms.md](docs/source-terms.md) | What each source's terms allow to be stored and fetched |
| [tooling/README.md](tooling/README.md) | Optional development tools: agent coordination, Context7, OpenSpec, Promptfoo, browser checks, tracing |
