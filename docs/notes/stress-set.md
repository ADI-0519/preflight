# Stress set: harder renders of the dev reconstructions

A reconstruction is built from the ASA's ad description, which quotes the challenged claim exactly, so the claim reaches the screen as a clean caption or clear synthetic speech on a still. Real ads hide claims in speech over music, small print, text split across cuts, compressed video or pictures. The stress set measures how much of the checker's dev recall depends on that legibility. It is a dev figure only (`docs/product-rules.md`, rule 5).

## How it was built

Each of the 25 ruled ads in split v2 dev was rendered again in five ways, from its own `shotlist.json` and saved stills: no new claim, no new picture, no image-model call (rule 8). The "AI reconstruction from ASA ruling text" label stays on every render (rule 9). Variants are not split items; each is scored against its parent's ground truth, and `claim_recall_carried` counts the claims the plain reconstruction carried, as on the plain runs. Code: `src/preflight/eval/stress.py`; renders in git-ignored `data/raw/stress/<kind>/<item>/`.

| Kind | Change | Applies to |
|---|---|---|
| `music` | a synthetic chord bed made by ffmpeg, 12 dB under the voiceover's mean level | the 13 video ads |
| `speech_only` | every on-screen line carrying a ground-truth claim leaves the screen and joins that scene's voiceover | 12 video ads (A24-1241024 shows no claim on screen) |
| `small_text` | captions at 14 points (about 40% of the plain size), no box, lower left; on video one line a second, on a still every line at once | all 25 |
| `split_cuts` | each claim line is cut in the middle of each claim it carries, and the pieces alternate between two consecutive scenes with the same still | 24 (A24-1241024 has no line to cut) |
| `compressed` | the plain render re-encoded at 480 lines: video at 300 kb/s, stills as low-quality JPEG | all 25 |

A kind that cannot apply to an ad is skipped and listed in the run's CSV, so it is never read as a catch or a miss. `split_cuts` leaves 34 claims whole on some screen across 15 ads (one-word claims such as "Focus", hashtags, claims repeated elsewhere); they are listed in each ad's `whole_claims.txt`.

Each kind was screened end to end with judge_v7, `--no-align`, once with a single judge sample and once voting over three, and registered with stage `stress`. Each run also registers the plain run's figures on the same ads (`plain_ad_recall`, `plain_claim_recall_carried`) and the claims and ads that flipped. Plain baselines: `screen-20261102T210524` (single sample) and `screen-20261102T211550` (voting).

## Results

Carried claims caught with a matching rule, harder render against plain render on the same ads, with 95% intervals over ads.

| Kind | Judge | Run | Ads | Claims caught | Plain | Lost / gained | Ads caught (plain) |
|---|---|---|---|---|---|---|---|
| `music` | single | `stress-music-20261102T230051` | 13 | 98/136 [0.62, 0.82] | 102/136 [0.68, 0.81] | 10 / 6 | 13/13 (13/13) |
| `music` | vote | `stress-music-20261102T232658` | 13 | 101/136 [0.67, 0.81] | 102/136 [0.68, 0.81] | 6 / 5 | 13/13 (13/13) |
| `speech_only` | single | `stress-speech_only-20261102T224432` | 12 | 85/130 [0.54, 0.75] | 98/130 [0.69, 0.81] | 20 / 7 | 12/12 (12/12) |
| `speech_only` | vote | `stress-speech_only-20261102T231744` | 12 | 86/130 [0.54, 0.76] | 98/130 [0.68, 0.81] | 19 / 7 | 12/12 (12/12) |
| `small_text` | single | `stress-small_text-20261102T225640` | 25 | 190/238 [0.74, 0.86] | 193/238 [0.76, 0.86] | 14 / 11 | 25/25 (25/25) |
| `small_text` | vote | `stress-small_text-20261103T002847` | 25 | 191/238 [0.73, 0.87] | 194/238 [0.76, 0.87] | 14 / 11 | 25/25 (25/25) |
| `compressed` | single | `stress-compressed-20261103T010631` | 25 | 189/238 [0.71, 0.88] | 193/238 [0.76, 0.86] | 17 / 13 | 25/25 (25/25) |
| `compressed` | vote | `stress-compressed-20261103T000531` | 25 | 192/238 [0.73, 0.89] | 194/238 [0.76, 0.87] | 14 / 12 | 25/25 (25/25) |
| `split_cuts` | single | `stress-split_cuts-20261102T232611` | 24 | 66/232 [0.17, 0.41] | 189/232 [0.76, 0.87] | 130 / 7 | 16/24 (24/24) |
| `split_cuts` | vote | `stress-split_cuts-20261103T004439` | 24 | 67/232 [0.18, 0.41] | 190/232 [0.76, 0.87] | 130 / 7 | 17/24 (24/24) |

Ads no longer caught under `split_cuts`: A24-1238193 (video), A24-1239908, A24-1239907, A24-1241337, A24-1231792, A24-1229687 and A23-1191380 (stills), and A24-1241017 on the single-sample run only. No other kind lost or gained an ad. By format, `split_cuts` caught 59 of 130 carried claims on video against 98 plain, and 7 of 102 on stills against 91 (single sample).

## What it shows

- **Music, small print and compression cost little.** Each loses 1 to 4 carried claims net out of 136 to 238, within the run-to-run noise of 8 to 12 claims (`docs/notes/decisions.md`, P66), and no ad.
- **Claims heard but not shown cost about a tenth.** With every claim line moved from the screen into speech, 13 of 130 carried claims are lost net (12 with voting), and every ad is still caught.
- **Claims split across cuts or cards cost most of the recall.** On stills, each card of a split ad is screened as its own ad, so a claim cut across two cards never reaches the judge whole: 7 of 102 caught. The scoring adds to this, since a catch needs one flagged claim holding the whole ground-truth claim, so two flagged halves count as a miss. On video the voiceover still speaks every claim in full, yet 39 of 98 claims are lost; the reason is not yet known.
- **Voting changes none of these by more than 4 claims.**

## What it means for the test figures

The test reconstructions are built the same way as the plain dev renders, so the P33 test figures are an upper bound on legible ads. On dev, harder sound, smaller print and lossy compression move recall by no more than the noise, and claims carried only in speech cost about a tenth. An ad that splits a claim across carousel cards or cuts is the case the checker handles worst: there, recall on these ads fell from about 80% to under 30%, and a third of the ads were not caught at all. Quote the test recall with that limit beside it.

## Open

- Why `split_cuts` loses claims on video while the voiceover still carries them (extraction or scoring).
- Whether a carousel should be screened as one ad, with its cards read together, rather than card by card.
- Scoring a split claim as caught when every piece of it is flagged, with the P70 line match (`docs/notes/noise-lines.md`).
