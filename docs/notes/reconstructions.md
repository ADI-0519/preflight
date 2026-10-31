# Reconstructions (P15)

Built 31 Oct 2026 by `preflight.eval.reconstruct` from the ruling items in the draft split v1 (P14, not yet frozen). Outputs are in `data/raw/reconstructions/<ruling-id>/` (git-ignored); nothing generated is committed.

## How they are built

- **Input:** `AdDescription` holds the ruling ID and the "Ad description" section only. It forbids extra fields, and the builder rejects anything else (`docs/plan.md`, evaluation protocol item 3; rule 8). Tests check that no assessment, issue or action text reaches any model request.
- **Shot list:** `muse-spark-1.3`, Standard mode, low reasoning effort, strict JSON schema, prompt `prompts/reconstruct_shotlist_v1.txt`. The prompt:
  - carries quoted wording exactly and invents nothing for `[…]`;
  - replaces brand and person names with generic ones;
  - picks a video when the description mentions speech, video, TikTok and similar, and an image otherwise.
- **Stills:** `muse-image-1.0`, one per scene, asked for no text in the image. All wording is drawn on afterwards with ffmpeg, so it stays exact.
- **Voiceover:** local Piper TTS (`en_GB-alan-medium`), video items only, installed with `uv sync --group fixtures` (decided in P05).
- **Label:** "AI reconstruction from ASA ruling text" is drawn on every frame and set in `meta.json` (`reconstruction: true`). Long on-screen text is shrunk to fit, not cut.

## Run of 31 Oct 2026

| | |
|---|---|
| Ruling items in split v1 | 74 |
| Built | 72 (37 image, 35 video; 179 scenes) |
| Failed | 2: A25-1281264 and A26-1341476, refused by Meta's content filter ("prompt triggering our content management policy") |
| Cost | $2.57 at published prices (about $0.04 per item) |
| Time | about 62 minutes, one item at a time |

The two refusals have no reconstruction, so the evaluation either drops them from v1 or replaces them before the freeze. Rerunning with `--only <id> --rebuild` retries one item.

A check for advertiser names in the shot lists found none: two hits were ordinary words ("drop", "top 5 supplements").

Video items run longer than the prompt's 40 seconds when the quoted voiceover is long, because each scene lasts as long as its speech.

## Still to do

- **Spot-check by two founders**, as product rule 8 requires before any reconstruction is used: wording carried exactly, nothing added, no brand or likeness. Record who checked which items here.
- **Gate 1:** `docs/notes/decisions.md` says the organisers' answer on gate 1 is needed before P15. It has not arrived. These reconstructions stay local and unpublished until it does.

## Rebuild

```
uv sync --group fixtures
uv run --group fixtures python -m preflight.eval.reconstruct eval/splits/v1.yaml
```

This needs `META_API_KEY` in `.env`, ffmpeg on PATH and the cached ruling pages in `data/raw/rulings/`. Built items are skipped unless `--rebuild` is passed.
