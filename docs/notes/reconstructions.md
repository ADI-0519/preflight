# Reconstructions (P15)

Built 31 Oct 2026 by `preflight.eval.reconstruct` from the 74 ruling items in split v1 (P14; frozen since, with the same items). Outputs are in `data/raw/reconstructions/<ruling-id>/` (git-ignored); nothing generated is committed.

## How they are built

- **Input:** `AdDescription` holds the ruling ID and the "Ad description" section only. It forbids extra fields, and the builder rejects anything else (`docs/plan.md`, evaluation protocol item 3; rule 8). Tests check that no assessment, issue or action text reaches any model request.
- **Shot list:** `muse-spark-1.3`, Standard mode, low reasoning effort, strict JSON schema, prompt `prompts/reconstruct_shotlist_v1.txt`. The prompt:
  - carries quoted wording exactly and invents nothing for `[…]`;
  - replaces brand and person names with generic ones;
  - picks a video when the description mentions speech, video, TikTok and similar, and an image otherwise.
- **Stills:** `muse-image-1.0`, one per scene, asked for no text in the image. All wording is drawn on afterwards with ffmpeg, so it stays exact. If Muse Image refuses a scene's picture, the builder uses a neutral product shot instead and lists the scene in `meta.json` under `fallback_stills`; the scene's wording is unchanged.
- **Voiceover:** local Piper TTS (`en_GB-alan-medium`), video items only, installed with `uv sync --extra render` (chosen in P05, moved to the `render` extra in P41).
- **Label:** "AI reconstruction from ASA ruling text" is drawn on every frame and set in `meta.json` (`reconstruction: true`). Long on-screen text is shrunk to fit, not cut.

## Run of 31 Oct 2026

| | |
|---|---|
| Ruling items in split v1 | 74 |
| Built | 74 (38 image, 36 video) |
| Picture refused by Muse Image | 2 on the first run. A25-1281264 went through on a rebuild with a new shot list. A26-1341476 (a before-and-after drawing of a bottom) uses the fallback picture, so the imagery that ruling partly rests on is not in its reconstruction. |
| Cost | $2.64 at published prices (about $0.04 per item) |
| Time | about 65 minutes, one item at a time |

Video items run longer than the prompt's 40 seconds when the quoted voiceover is long, because each scene lasts as long as its speech.

## Automatic check

`uv run python -m preflight.eval.check_reconstructions` compares each reconstruction's wording with its ad description and ground truth (no model calls; results in `data/raw/reconstructions/_check.json`).

- **Claims carried:** 763 of 799 ground-truth claims, 735 word for word and 28 near (a brand swapped for "[brand]" or a "[sic]" dropped).
- **Claims missing: 36, in 23 items.** Every one contains a brand, product or person's name, which the shot-list prompt genericises (rule 3 of the prompt, to keep real brands and likenesses out). Some of those names are claims in themselves: product names ("Happy Mind", "GuLP-1", "PROstate Support"), doctor endorsements ("DR. ... BOARD-CERTIFIED UROLOGIST") and comparisons with named drugs ("Ozempic"). A screener cannot flag them in the reconstruction, so P31 should either score those claims as not reconstructable or a prompt v2 should keep claim-bearing names. **Founders to decide.**
- **Lines not from the ad description:** 7 of 891, in 5 items, all genericised names ("Meet the product by [brand]") or testimonial attributions ("– Customer"). None adds a claim.

## Spot-check (product rule 8)

Two checkers check each item below before reconstructions are used in any run: the wording is carried exactly, nothing is added, and no real brand or person's likeness appears. The list is from the rebuild of 3 Nov 2026: every item the automatic check flagged (31) plus the same 10 of the others drawn at random in the first build (seed 15). A checker is a founder, or an independent checker as in `docs/notes/decisions.md` (4 Nov 2026, P33). Open `data/raw/reconstructions/<id>/` next to the ruling page, and put your name in a column when the item passes, or a note when it does not.

| Item | Split | Format | Claims carried | Why checked | Checker 1 | Checker 2 |
|---|---|---|---|---|---|---|
| A24-1228813 | dev | video | 3 of 5 | 2 claim(s) missing | checker: passes | checker: passes |
| A24-1231792 | dev | image | 4 of 6 | 2 claim(s) missing | checker: passes | checker: passes |
| A24-1238193 | dev | video | 4 of 6 | 2 claim(s) missing | checker: passes | checker: fails |
| A24-1239904 | dev | video | 23 of 24 | 1 claim(s) missing | checker: passes | checker: passes |
| A24-1239905 | dev | video | 27 of 28 | 1 claim(s) missing | checker: passes | checker: passes |
| A24-1241022 | dev | image | 27 of 27 | 1 added line(s) | checker: passes | checker: passes |
| A24-1241023 | dev | image | 12 of 13 | 1 claim(s) missing | checker: passes | checker: passes |
| A24-1242030 | test | image | 3 of 4 | 1 claim(s) missing | checker: fails | checker: fails |
| A24-1251814 | test | image | 8 of 10 | 2 claim(s) missing | checker: fails | checker: fails |
| A24-1269415 | test | video | 5 of 6 | 1 claim(s) missing, 1 added line(s) | checker: passes | checker: passes |
| A25-1279959 | test | image | 10 of 11 | 1 claim(s) missing | checker: fails | checker: fails |
| A25-1281257 | test | video | 23 of 25 | 2 claim(s) missing | checker: fails | checker: fails |
| A25-1281265 | test | image | 11 of 13 | 2 claim(s) missing | checker: fails | checker: fails |
| A25-1281266 | test | video | 12 of 12 | 2 added line(s) | checker: passes | checker: passes |
| A25-1289625 | test | image | 3 of 3 | 1 added line(s) | checker: passes | checker: passes |
| A25-1303537 | test | image | 4 of 5 | 1 claim(s) missing | checker: passes | checker: passes |
| A25-1303555 | test | video | 25 of 27 | 2 claim(s) missing | checker: passes | checker: passes |
| A25-1303556 | test | image | 9 of 10 | 1 claim(s) missing | checker: fails | checker: passes |
| A25-1303750 | test | image | 1 of 2 | 1 claim(s) missing | checker: passes | checker: passes |
| A25-1313821 | test | image | 14 of 15 | 1 claim(s) missing | checker: passes | checker: passes |
| A25-1313823 | test | video | 38 of 39 | 1 claim(s) missing | checker: passes | checker: passes |
| A25-1317723 | test | image | 11 of 12 | 1 claim(s) missing | checker: passes | checker: passes |
| A26-1325179 | test | video | 43 of 48 | 5 claim(s) missing, 1 added line(s) | checker: passes | checker: fails |
| A26-1330390 | test | video | 11 of 12 | 1 claim(s) missing | checker: fails | checker: fails |
| A26-1341476 | test | image | 4 of 4 | fallback picture | checker: passes | checker: passes |
| G23-1215538 | dev | video | 4 of 5 | 1 claim(s) missing | checker: fails | checker: fails |
| G24-1241706 | dev | video | 8 of 10 | 2 claim(s) missing, fallback picture | checker: passes | checker: passes |
| G24-1248968 | dev | video | 14 of 15 | 1 claim(s) missing | checker: passes | checker: passes |
| G24-1252527 | test | image | 11 of 14 | 3 claim(s) missing | checker: fails | checker: fails |
| G25-1323444 | test | image | 16 of 18 | 2 claim(s) missing, 2 added line(s) | checker: fails | checker: fails |
| G26-1339905 | test | video | 2 of 3 | 1 claim(s) missing | checker: passes | checker: passes |
| A23-1191380 | dev | image | 3 of 3 | random sample | checker: fails | checker: fails |
| A23-1196136 | dev | video | 6 of 6 | random sample | checker: passes | checker: passes |
| A23-1202159 | dev | video | 12 of 12 | random sample | checker: passes | checker: passes |
| A23-1216841 | dev | image | 8 of 8 | random sample | checker: passes | checker: passes |
| A24-1240828 | dev | image | 5 of 5 | random sample | checker: passes | checker: passes |
| A24-1240834 | test | video | 7 of 7 | random sample | checker: passes | checker: passes |
| A24-1241024 | dev | video | 6 of 6 | random sample | checker: passes | checker: passes |
| A24-1243213 | dev | video | 10 of 10 | random sample | checker: passes | checker: passes |
| A25-1303746 | test | video | 7 of 7 | random sample | checker: passes | checker: passes |

Reading reconstructions of test items means reading test-split ad wording, so the checkers should stay off prompt and few-shot work (rule 5), as for the ground truth.

## Still to do

- **Gate 1:** `docs/notes/decisions.md` says the organisers' answer on gate 1 is needed before P15. It has not arrived. These reconstructions stay local and unpublished until it does.
- **Spot-check** above, by two checkers.
- **Names that carry claims:** the decision above.

## Rebuild

```
uv sync --extra render
uv run --extra render python -m preflight.eval.reconstruct eval/splits/v1.yaml
```

This needs `META_API_KEY` in `.env`, ffmpeg on PATH and the cached ruling pages in `data/raw/rulings/`. Built items are skipped unless `--rebuild` is passed.
