# Screening workspace (P52)

The React/TypeScript page uses the P51 API. It makes no model calls itself and stores
no keys, ad content or decisions in browser storage. FastAPI serves the Vite build.
This remains a localhost, single-process prototype. Firebase sign-in with an emailed
code is available when configured; otherwise the workspace runs without sign-in.
With sign-in, each account sees and opens only its own uploads and screenings, listed
under "Your screenings" on the start page; without it, the workspace is shared. See the
authentication setup in the README.

The product page includes an illustrative synthetic evidence example, supported
creative types, a review walkthrough, data handling, FAQs and a closing action.
The footer links to these sections, the API documentation and the account pages.
Content uses PreFlight's actual capabilities; it does not borrow another site's
copy, artwork, customer endorsements or performance claims.

Product copy names the task directly: upload an ad, check its claims and review
the evidence. It describes flags as possible issues, not verified breaches, and
does not promise a fast result or automatic editing of an uploaded video. The
upload notice distinguishes expiry from local deletion: cleanup requires a running
server and may wait for active jobs. No model accuracy claim follows from a
successful browser journey.

With Firebase sign-in disabled, `/login` and `/signup` are directly addressable account **page previews**, served
with the same build checks and content security policy as `/`. They do not implement
authentication, create accounts or protect uploads. Their forms are disabled, explain
that accounts are not connected, and do not collect credentials. They link to one
another and back to the local desk. A real account rollout needs an agreed identity
provider plus ownership/access controls for uploads, jobs, reports and revisions.
With sign-in enabled, uploads, jobs, reports and revisions belong to the account that
created them, and the real sign-in flow replaces
the previews and runs before the workspace loads.

The entry screen accepts one file through the chooser or drag-and-drop, explains
the review workflow and keeps upload terms visible. Format/retention details
expand on demand. The media and evidence panels use the same source-backed data
as the report; appearance changes do not change screening results. See the
[4 November design research](notes/p52-design-research.md#workspace-refresh-4-november-2026).

## Run

Requires Node 24, Python 3.12, uv, FFmpeg and FFprobe.

```powershell
uv sync --locked --extra api --extra page --extra mcp
npm ci --prefix web
npm --prefix web run build
uv run uvicorn preflight.api:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

Open `http://127.0.0.1:8000/`. If another server is already running, restart it after
backend changes or choose another port. A missing web build returns 503 at `/`;
the API remains available at `/docs`. Build before starting the server so its assets
mount exists. For frontend development, `npm --prefix web run dev` serves Vite on
localhost and proxies API/SSE requests to port 8000. Keep the backend local.

Upload an image, video or UTF-8 script, follow server-sent stage events and choose a claim in the
timeline. Selection seeks the video and shows the exact cited evidence, crop where
available, dated source provenance and verbatim suggested register wording. Missing
assets are labelled unavailable. Incomplete screens never become clean results.
The report link opens the existing source report. Job URLs support reloading retained
results; expired resources require another upload. There is no progress polling.
While a job runs, the uploaded ad stays on screen beside the stages the server has
reported. Loaded results open in a media-first workspace. **Evidence** shows the ad
above a claim track: one keyboard-selectable row per claim, with its start time, its
words and, for video, its evidence spans on the ad's time axis (overlapping claims keep
their own rows). The rows come from the same view as the HTML report and the agent
tools (`preflight.view`): a flagged phrase inside a longer flagged claim on the same
evidence folds into that claim's row, so a row is a line of the ad, and an on-screen
line with no time read shows "Time not read" (a still, "Still") rather than 0:00.0.
Beside it, the inspector opens on the ad's words and the register's exact wording with
its register ID, or says that no replacement wording was suggested; the line's CAP rules follow,
section 15 first, then each flag's reason, sources and evidence. Phrases folded into the
line are listed under it with their own flags; a source the line already shows in full
is named only. "What you may say" opens the register's authorised entries for
the line's substance, quoted exactly with ID and conditions, separate from the
suggested wording. Stages that did not finish are named under the headline. **Prepare revision** shows the chosen scene
still beside the editable-scene form, with each flagged line's register wording and the
register's authorised entries for every flagged substance.
Completed fixes open **Compare rounds**, where a selector on each column exposes every
saved round and changed caption/voiceover lines are underlined. The Evidence view
continues to show the final saved screening. The full source report is available from
every review view. The page opens in light appearance, and the
header switches between dark and light appearance for the page session; no ad data or
preference is persisted locally. The design is described in
[the design research](./notes/p52-design-research.md). Inter Variable v4.1 is self-hosted
from the [upstream Inter project](https://github.com/rsms/inter/tree/v4.1), with its
SIL Open Font Licence under `web/src/fonts/`. It is loaded locally, without a runtime
font-provider request. Source Serif 4, already licensed and bundled in the repository,
is used for entry headings; evidence and controls remain in Inter. Light appearance
uses chalk/white surfaces, ink text and a deep petrol accent, with fine borders and
shallow shadows. Dark appearance retains steel surfaces and a copper accent.
Evidence highlights remain distinct from the labelled red/amber review tiers.
Dark appearance remains available through the header. The split entry layout puts
the introduction beside the upload desk, with the workflow underneath; phones
stack these sections and omit the decorative illustration to keep the upload action
within the initial viewport. The interface does not use background glow or backdrop blur.
The full screening notice stays in a sticky header with the top bar while scrolling.
Native EventSource reconnect resumes progress after a dropped connection. Invalid
progress data shows a recovery message and releases controls; reload the retained
job to recover its result. Starting another ad clears the previous draft editor.

To fix a fresh ad, supply an editable scene: a clean still plus actual captions and,
for video, voiceover. The web form currently supports one scene; the API supports
up to ten. Rendering does not recover editable layers from an opaque uploaded video.
Video speech requires `uv sync --extra api --extra render` and the existing P41
voice model setup. Fixing re-screens each draft and shows the saved rounds side by
side. A clean, completed final draft can be reviewed explicitly by a person: their
name, confirmation and optional note record a decision in the private audit. A saved
decision survives reload; flagged/incomplete/already-decided drafts have no approval
action. The supplied name is not an authenticated identity or a Meta verdict.

Uploads and derivatives follow [the API retention policy](./api.md). Live screening
needs the ignored ASA cache as well as Standard-mode model credentials. None are
required to build the page or run the replay-backed browser tests.

## Demo assets and reveal

The default demo directory is ignored `data/raw/demo/`. P53 owns selection of the
three final reconstructions and a fresh ad. No actual competition examples are
selected by this feature, and no held-out labels are read to tune the UI or models.
An operator supplies `items.json`, a JSON array such as:

```json
[
  {
    "id": "selected-ruling",
    "title": "Labelled reconstruction · <actual ruling ID>",
    "kind": "reconstruction",
    "ruling_id": "<actual ruling ID>",
    "screening": "selected/screening.json",
    "media": "selected/reconstruction.mp4",
    "crops": "crops"
  }
]
```

`scripts/build_demos.py <run_id> <item_id>...` writes this directory from a registered
run's own screenings, so a demo shows that run's blind result. It refuses an item outside
the part the run screened, a void or unregistered run, a screening that fails source
verification, and media whose content hash is not the file the run screened. It needs the
run's `data/work/runs/<run_id>/` screenings and each screened file's ingest folder
(`data/work/<content hash>/crops/`), which stay on the machine that ran it. Titles say
whether the item is a reconstruction or a team-written ad, and which split part it is from.

Media/screening paths are relative to the demo directory. The crops directory is
relative to the screening JSON's parent. Every asset must resolve inside the demo
root, including symlinks. Screening JSON is validated against repository snapshots
before presentation. Reconstructions must be labelled, branding removed and sourced
under product rules 8 and 9. Titles and IDs come from this explicit manifest, never
discovery of private uploads. A `kind: synthetic` fixture has no ASA outcome.

The reveal action reads outcome, date and CAP rules from the committed metadata
snapshot named in the screening, rather than trusting arbitrary manifest wording.
Ruling outcomes are separate from the recorded screening result. The frontend does
not send either result to a model. The browser tests supply three clearly labelled
synthetic replay states; these are UI contract cases, not the final demo assets.

## Scoreboard provenance

Until P33 selects a registered final test run, the page explicitly shows that no
final scoreboard is available. It never substitutes a dev run or replay count.

The selection format in `results/final.md` is one standalone line:

```text
run_id: <registered-screen-run-id>
```

`python -m preflight.eval.final` writes this line when exactly one of the runs it is
given is a test screening run, and omits it otherwise. The current file names
`screen-20261104T052428`.

The API joins this ID to `results/runs.csv` and requires `part=test`, `stage=screen`
and consistent run metadata. Displayed metrics retain their registered numerators,
denominators and confidence intervals, with run ID, split and revision. Zero
denominators show “Not measured”. Cost, timing and flags-per-ad metrics are not
misrepresented as percentages. Synthetic test registries live only in temporary
directories; no real final run is created or modified by this work.

## Verification

```powershell
npm --prefix web run build
npm --prefix web test
npm --prefix web run test:browser
uv run pytest tests/test_web_api.py tests/test_api.py -q
uv run ruff check
uv run pytest -m "not live"
uv run python scripts/verify_agent_setup.py
```

The browser suite starts a real Uvicorn server on port 8011, serves the production
build and exercises HTTP uploads, SSE, recorded screening, the real fix loop and an
explicit synthetic review record. Model transports reject network access. The video
recordings combine the existing clip and separate speech fixture; P41 round recordings
exercise orchestration rather than establish that the displayed clip produced those
rounds. These checks do not establish live accuracy, final held-out metrics, voiced
video rendering, public deployment or final P53 asset readiness.

Recovery cases also cover invalid progress, delayed reveal responses, expired jobs,
editor reset, disconnected streams and long demo titles on mobile. See the
[user-verification report](./reviews/p52-user-verification-2026-11-01.md) for the
separate live synthetic image/video checks and their limits.
