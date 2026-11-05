# Web workspace

The workspace is a React and TypeScript page in `web/`, built by Vite and served by the FastAPI service at `/`. It is a client of the [screening API](api.md): it calls no model itself, holds no keys, and keeps no ad content or decisions in browser storage. It runs as one process with the API, locally or on Cloud Run ([deploy.md](deploy.md)).

## Run

Requires Node 24, Python 3.12, uv, FFmpeg and FFprobe.

```powershell
uv sync --locked --extra api --extra page --extra mcp
npm ci --prefix web
npm --prefix web run build
uv run uvicorn preflight.api:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

Open <http://127.0.0.1:8000/>. Build before starting the server: without a build, `/` returns 503 `web_build_missing`, while the API stays available at `/docs`. Restart the server after backend changes.

For front-end work, run the API as above and `npm --prefix web run dev` alongside it. Vite serves the page on localhost and proxies `/ui`, `/uploads`, `/screenings`, `/jobs`, `/fixes` and `/health` to port 8000.

Live screening needs `META_API_KEY` and the cached ruling pages described in [api.md](api.md#run). Building the page and running its tests need neither.

## Sign-in

With `FIREBASE_PROJECT_ID` unset, the workspace opens without sign-in and everyone on the server shares it. `/login` and `/signup` then show disabled previews of the account pages; they collect no credentials and protect nothing.

With sign-in configured, the sign-in flow runs before the workspace loads: a Firebase account, then a 6-digit code sent by email ([api.md](api.md#sign-in-and-ownership)). Each account sees only its own uploads and screenings, listed on the start page under "Your screenings", where a screening can be renamed or retried.

## Using it

The start page takes one file, by the file chooser or drag and drop: an image, an MP4 or MOV video, or a UTF-8 `.txt` or `.md` script. The page checks the type before sending, names the reason when it refuses a file, and sends large files in parts. The upload notice states how long the files are kept.

While a screening runs, the ad stays on screen beside the stages the server has reported. Progress arrives over server-sent events and resumes after a dropped connection. A job's URL reloads its result for as long as the upload is retained.

A finished screening opens in three views:

| View | What it shows |
|---|---|
| Evidence | The ad above a claim track, one row per flagged line with its start time, words and evidence spans on the ad's time axis. Selecting a row seeks the video and opens the inspector: the ad's words, the register's exact wording with its ID (or a statement that none was suggested), the line's CAP rules with section 15 first, and each flag's reason, sources and evidence. "What you may say" lists the register's authorised entries for the line's substance. |
| Prepare revision | The chosen scene's still beside an editable form for its captions and voiceover, with the register wording for each flagged line. |
| Compare rounds | After a fix, the saved rounds side by side, with changed caption and voiceover lines marked. |

Rows come from the same view of the screening as the HTML report and the agent tools, so a flagged phrase inside a longer flagged line on the same evidence folds into that line's row. An on-screen line with no time read shows "Time not read", and a still shows "Still". A script result shows the numbered source and moves to the evidence line when a claim is selected. Stages that did not finish are named under the headline, and an incomplete screening is never shown as a clean result. The full HTML report is linked from every view.

To fix an ad, supply an editable scene: a clean still with its real captions and, for video, its voiceover. The form takes one scene; the API takes up to ten. Editable layers cannot be recovered from an uploaded video. Voiced video needs the `render` extra. When the final round is complete and nothing is flagged, a person can choose "Record my review decision" to record their name and an optional note in the fix's audit. The decision survives a reload. Flagged, incomplete or already decided drafts offer no approval.

## Demos

Demos are recorded screenings shown without spending model credit. They load from `data/raw/demo/`, which git ignores. `scripts/build_demos.py <run_id> <item_id>...` writes the directory from a registered evaluation run's own screenings, so a demo shows that run's blind result. It refuses an item outside the part the run screened, a void or unregistered run, a screening that fails source verification, and media whose content hash differs from the file the run screened. It needs the run's screenings under `data/work/runs/<run_id>/` and each item's ingest folder, which exist only on the machine that ran it.

The directory holds an `items.json` manifest:

```json
[
  {
    "id": "example-ruling",
    "title": "Labelled reconstruction · <ruling ID>",
    "kind": "reconstruction",
    "ruling_id": "<ruling ID>",
    "screening": "example-ruling/screening.json",
    "media": "example-ruling/reconstruction.mp4",
    "crops": "crops"
  }
]
```

`kind` is `reconstruction`, which requires a `ruling_id`, or `synthetic`, which has none. Media and screening paths are relative to the demo directory, and `crops` to the screening's folder; every path must resolve inside the demo directory, symlinks included. Each screening is verified against the snapshots it names before it is shown. Reconstructions are labelled, carry no branding and show their ruling ID.

"Reveal ASA outcome" shows the ruling's outcome, date and CAP rules from the committed rulings snapshot that the screening names. It does not trust wording in the manifest, and it keeps the ruling's outcome separate from the screening's result.

## Scoreboard

The page shows the registered test run named in [results/final.md](../results/final.md), with the keyword baseline beside it. `python -m preflight.eval.final` writes two lines into that file, `run_id: <screen run>` and `baseline_id: <baseline run>`, and the API looks both up in [results/runs.csv](../results/runs.csv).

The screen run must be on a test part, with stage `screen`, a commit hash and the same metadata on every row; otherwise the page says that no final scoreboard is available, and it never substitutes a development run. The baseline column appears only when its run is a registered baseline on the same split. Each metric keeps its registered numerator, denominator and interval, and a zero denominator shows "Not measured". How the figures are produced is in [evaluation.md](evaluation.md).

## Tests

```powershell
npm --prefix web run build          # generate schema types, type-check, build
npm --prefix web run format:check
npm --prefix web test               # unit tests (Vitest)
npm --prefix web run install:browser
npm --prefix web run test:browser   # browser tests (Playwright, Chromium)
uv run pytest tests/test_web_api.py -q
```

The browser tests start a replay server on port 8011 that serves the production build. They exercise uploads, progress events, recorded screenings, the real fix loop, approval, scripts, demos, sign-in pages and recovery from failures, including invalid progress data, expired jobs and dropped streams. Part uploads are covered by the unit tests. Model transports refuse network access, so the tests check the page and the API contract. Model accuracy is measured separately ([evaluation.md](evaluation.md)). Screenshots and traces go to `data/work/web-browser-results/`.
