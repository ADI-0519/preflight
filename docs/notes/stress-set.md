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
| `split_cuts`, cards read together | single | `stress-split_cuts-20261103T013804` | 24 | 94/232 [0.29, 0.55] | 189/232 [0.76, 0.87] | 104 / 9 | 22/24 (24/24) |
| `split_cuts`, cards read together | vote | `stress-split_cuts-20261103T015225` | 24 | 95/232 [0.30, 0.55] | 190/232 [0.76, 0.87] | 102 / 7 | 22/24 (24/24) |

Ads no longer caught under `split_cuts`: A24-1238193 (video), A24-1239908, A24-1239907, A24-1241337, A24-1231792, A24-1229687 and A23-1191380 (stills), and A24-1241017 on the single-sample run only. No other kind lost or gained an ad. By format, `split_cuts` caught 59 of 130 carried claims on video against 98 plain, and 7 of 102 on stills against 91 (single sample).

The last two rows rerun `split_cuts` after a carousel's cards were read together as one slideshow (below, "Reading a carousel as one ad"). Stills rose from 7 to 35 of 102 carried claims (36 voting), video stayed at 59 of 130, and only A24-1238193 (video) and A24-1229687 (stills) are still not caught.

## What it shows

- **Music, small print and compression cost little.** Each loses 1 to 4 carried claims net out of 136 to 238, within the run-to-run noise of 8 to 12 claims (`docs/notes/decisions.md`, P66), and no ad.
- **Claims heard but not shown cost about a tenth.** With every claim line moved from the screen into speech, 13 of 130 carried claims are lost net (12 with voting), and every ad is still caught.
- **Claims split across cuts or cards cost most of the recall.** On stills, each card of a split ad is screened as its own ad, so a claim cut across two cards never reaches the judge whole: 7 of 102 caught. On video, 39 of 98 claims are lost net, because most claims a reconstruction shows on screen are never spoken. The scoring adds to both, since a catch needs one flagged claim holding the whole ground-truth claim, so two flagged halves count as a miss. The next section traces each lost claim.
- **Voting changes none of these by more than 4 claims.**

## Where claims are lost

`scripts/claim_losses.py` reads a stress run's saved screenings beside its plain baseline's, with no model call. A claim is lost when the plain run caught it with a matching rule and the stress run did not. The script places each lost claim at the first step it failed:

- **Read:** the claim is whole in the transcript or in one on-screen text. If it is not, the script asks whether its pieces are all on screen, within one screening or only across the screenings of one ad.
- **Extracted:** an extracted claim quotes it at any length. If none does, the script asks whether extracted claims hold its pieces.
- **Flagged:** that extracted claim carries a flag.
- **Rule:** the flag cites one of the claim's rules, or a rule above or below one.
- **Scored:** flagged with a matching rule and still not caught. Only an over-long quote reaches this step, since claim recall rejects a quote longer than twice the claim plus five words (`docs/notes/noise-lines.md`).

Separately, it counts the lost claims whose pieces were each flagged with a matching rule and together cover at least 80% of the claim's words, the P70 line match applied to recall.

Lost claims by step, single judge sample against `screen-20261102T210524`:

| Step | `split_cuts` stills | `split_cuts` video | `speech_only` |
|---|---|---|---|
| Not read | 0 | 1 | 6 |
| Shown in pieces across the ad's cards | 58 | – | – |
| Shown in pieces within one screening | 26 | 39 | 0 |
| Not extracted (pieces extracted) | 0 | 1 (0) | 4 (4) |
| Not flagged | 0 | 1 | 0 |
| Flagged with another rule | 0 | 0 | 2 |
| Flagged, quote too long to score | 0 | 4 | 8 |
| **Lost** | **84** | **46** | **20** |
| Every piece flagged with a matching rule | 16 | 11 | 10 |

The voting runs (`stress-split_cuts-20261103T004439`, `stress-speech_only-20261102T231744` against `screen-20261102T211550`) place every claim at the same step, apart from one more stills claim shown in pieces across cards, one fewer video claim in pieces and one fewer flagged with another rule. The "lost" totals are gross; the results table nets them against claims gained.

What each step shows:

- **Split stills: every loss happens before extraction.** Each lost claim was shown only in pieces. In 58 the pieces sit on different cards, which `preflight.eval.run.screen_item` screens as separate ads, so no screening holds the whole claim. In the other 26 the pieces share a card as separate lines, and extraction did not rejoin them. In 16 of the 84 the judge flagged every piece with a matching rule.
- **Split video: the claims were never spoken.** `split_cuts` cuts only on-screen lines, and 39 of the 46 lost claims were shown on screen and never spoken, so they reached the screening only as pieces on consecutive scenes. In 11 the judge flagged every piece with a matching rule. Four more were quoted whole inside a longer line and fail on length. Only two losses happen after reading and before flagging: A24-1239905/6 was not extracted, and A24-1239905/24 was extracted but not flagged.
- **Speech only: transcription and quote length.** Eight claims were flagged with a matching rule inside a spoken sentence too long to score; the render joins each moved line onto that scene's voiceover, so the claim arrives mid-sentence. Six were not transcribed in a form the match accepts: two hashtags spoken as "hash ultimate hangover cure", "out-vitamin" heard as "without vitamin", "Dr Paul O'Connell" heard as "doctor Paula", and two short lines absent from the transcript. Four were extracted only in pieces, and two were flagged under another rule.

So the losses come from three causes. The cards of one ad are screened apart (58 claims). Extraction does not rejoin a claim shown in pieces within one screening (65). Recall scoring needs one whole quote of bounded length (12 over-long quotes, and 37 claims whose flagged pieces cover them). The judge's own misses, a claim extracted whole but not flagged or flagged under another rule, are 3 of 150.

IDs are `<item>/<index of the claim in the item's ground truth>`, single judge sample.

- **`split_cuts` stills, pieces across cards (58):** A23-1191380/0; A23-1216841/2, /3, /4, /5, /6, /7; A24-1229687/0, /1, /2; A24-1231792/0, /1, /2, /3; A24-1239907/0, /1, /2, /3, /4, /5, /6, /7; A24-1239908/0, /1, /2, /3, /4; A24-1240828/0, /2; A24-1241017/0, /3, /4, /5; A24-1241022/0, /1, /2, /4, /6, /8, /11, /19, /26; A24-1241023/2, /3, /6, /9, /11; A24-1241337/0, /1, /2, /3, /6, /7; A24-1246372/0, /2, /3, /5, /10
- **`split_cuts` stills, pieces on one card (26):** A23-1191380/2; A24-1241017/2, /6; A24-1241022/3, /7, /9, /10, /12, /13, /14, /16, /17, /18, /20, /22, /23, /24, /25; A24-1241023/0, /4, /8, /10; A24-1241337/4, /5; A24-1246372/4, /7
- **`split_cuts` stills, every piece flagged (16):** A24-1229687/1, /2; A24-1239907/1; A24-1241017/2; A24-1241022/8, /12, /13, /16, /17, /23; A24-1241023/11; A24-1241337/1, /2, /4, /6; A24-1246372/0
- **`split_cuts` video, pieces on one ad's scenes (39):** A23-1196136/1; A23-1224570/3; A24-1238193/1, /2, /4; A24-1239904/1, /2, /7, /8, /9, /22; A24-1239905/2, /5, /11, /13, /14, /20, /21, /22, /25, /26; A24-1239910/2, /3; A24-1243213/0, /2; G23-1215538/0, /1; G24-1241706/1, /3, /4, /5; G24-1248968/0, /1, /2, /3, /4, /10, /11, /12
- **`split_cuts` video, other steps (7):** not read A24-1239905/15; not extracted A24-1239905/6; not flagged A24-1239905/24; quote too long A24-1239904/4, A24-1239905/10, /12, /18
- **`split_cuts` video, every piece flagged (11):** A24-1238193/2; A24-1239904/4; A24-1239905/10, /12, /18; A24-1243213/0; G23-1215538/0; G24-1241706/3, /5; G24-1248968/2, /3
- **`speech_only` (20):** not read A23-1224570/1, A24-1228813/2, /3, A24-1239904/2, A24-1239905/10, G24-1241706/3; pieces extracted only A23-1224570/6, A24-1243213/0, /4, G23-1215538/0; another rule A24-1239905/24, G23-1215538/1; quote too long A23-1196136/5, A23-1202159/7, A24-1239904/9, A24-1239905/17, /18, A24-1239910/0, /4, /5
- **`speech_only`, every piece flagged (10):** A23-1196136/5; A23-1202159/7; A24-1239904/9; A24-1239905/17, /18; A24-1239910/0, /4, /5; A24-1243213/0; G23-1215538/0

## Reading a carousel as one ad

The breakdown above showed that 58 stills claims were lost because each card was screened as its own ad. `preflight.ingest.ingest_cards` now renders an ad's cards, in order, as one silent slideshow (3 seconds a card, so card k spans 3k to 3k + 3 seconds) and ingests it through the video path. `screen_item` screens an item's media as one ad, and `preflight screen a.png b.png` screens a carousel from the command line. No plain dev reconstruction has more than one image, so the plain baselines are unchanged; the change reaches only multi-card ads.

Lost claims by step after the change (`scripts/claim_losses.py`, single sample against `screen-20261102T210524`; voting differs by at most two claims a step):

| Step | Stills before | Stills after | Video (unchanged) |
|---|---|---|---|
| Not read | 0 | 4 | 1 |
| Shown in pieces across the ad's cards | 58 | – | – |
| Shown in pieces within one screening | 26 | 48 | 39 |
| Not extracted (pieces extracted) | 0 | 6 (4) | 1 (0) |
| Not flagged or flagged with another rule | 0 | 0 | 1 |
| Flagged, quote too long to score | 0 | 0 | 4 |
| **Lost** | **84** | **58** | **46** |
| Every piece flagged with a matching rule | 16 | 7 | 11 |

With every card in one screening, the stills losses are now the same kind as the video losses: a claim shown in pieces that extraction does not rejoin (87 of 104). The four stills claims not read and six not extracted are all in A24-1241022, a 27-claim ad whose cards hold many short lines.

## What it means for the test figures

The test reconstructions are built the same way as the plain dev renders, so the P33 test figures are an upper bound on legible ads. On dev, harder sound, smaller print and lossy compression move recall by no more than the noise, and claims carried only in speech cost about a tenth. An ad that splits a claim across carousel cards or cuts is the case the checker handles worst. With a carousel's cards read together, recall on these ads falls from about 80% to about 40%, and 2 of 24 ads are not caught; before that change it fell under 30%, with a third of the ads missed. Quote the test recall with that limit beside it.

## Open

- The API upload and the web page still take one file; a carousel is screened from the command line or the eval harness only. Evidence on a carousel is reported by time, not by card.
- Whether claim extraction should rejoin a claim shown in pieces within one screening (87 claims once a carousel is read as one ad). That is a prompt change, written from dev material only.
- Scoring a split claim as caught when every piece of it is flagged, with the P70 line match (`docs/notes/noise-lines.md`), and whether an over-long quote of a whole claim counts (37 and 12 lost claims). Either changes a measurement.
