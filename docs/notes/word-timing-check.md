# Word timing check (P24)

Checked 31 Oct 2026 on `data/raw/smoke/ad.mp4`, our own 30 s test ad: a synthetic voiceover with music under it. No customer material.

## Setup

- Transcript from Muse Voice Transcribe (`muse-voice-transcribe-1.0`), which gives turns with start and end times and no word times.
- Word times from torchaudio's MMS forced aligner (`MMS_FA`, `forced_align`), torch 2.15.0 and torchaudio 2.11.1, CPU, installed with `uv sync --extra align`. The model weights are fetched once into the torch hub cache; alignment runs locally, so only Voice Transcribe receives the audio.
- Each turn is aligned alone on its own audio, padded by 0.25 s each side. A segment is a phrase: a run of words ending at `.`, `!` or `?`, or at a gap of 0.3 s or more between aligned words.
- Without the extra, or when alignment fails or scores below the threshold, a segment keeps its turn's start and end and has `timing = "turn"`.

## Alignment score and threshold

The score is the median over letters of each letter's mean frame probability in the forced alignment. The mean was tried first and is dragged down by slurred letters (the right transcript scored 0.28 to 0.45, close to wrong ones).

| Audio | Transcript | Median | Mean |
|---|---|---|---|
| smoke ad, turn 0 (13.7 s) | its own | 0.50 | 0.45 |
| smoke ad, turn 1 (2 s) | its own | 0.48 | 0.31 |
| `speech.wav` fixture (2.8 s) | Voice Transcribe's own (partly garbled) | 0.42 | 0.28 |
| smoke ad, turn 0 | its words shuffled | 0.0006 | 0.19 |
| smoke ad, turn 0 | unrelated sentence | 0.24 | 0.24 |
| smoke ad, turn 1 | unrelated sentence | 0.00001 | 0.07 |
| `speech.wav` | unrelated sentence | 0.0006 | 0.10 |
| smoke ad, turn 1 | its words shuffled | 0.43 | 0.26 |

`MIN_SCORE = 0.35` sits between the lowest right pairing (0.42) and the highest wrong one that is not a reordering (0.24). A five-word turn shuffled keeps nearly the same letters in similar places and scores 0.43, so the score cannot catch a reordering of a short turn.

## Segments on the smoke ad

Each segment was cut from `audio.wav` at its start and end with ffmpeg and sent back through Voice Transcribe. "Words matched" means the clip's transcript has the same words with none missing at either edge.

| Segment | Turn | Start | End | Timing | Words matched |
|---|---|---|---|---|---|
| 0 | 0 | 0.14 | 4.82 | word | yes |
| 1 | 0 | 5.82 | 8.85 | word | yes |
| 2 | 0 | 9.81 | 11.99 | word | yes |
| 3 | 0 | 12.97 | 13.47 | word | yes |
| 4 | 1 | 14.53 | 15.74 | word | yes (a repeated "brighter" came back once) |

The clip transcript also drops the stumble "the the" in segment 0 and writes "Brightleaf" for "Bright Leaf". These are transcriber differences, not clipped edges. Turn 0 ends at 13.74 s in Voice Transcribe's own times; the aligned last word ends at 13.47 s.

Voice Transcribe returned the first 14 s as a single turn, so the phrase split rests entirely on the aligner's word times and punctuation.

## Reconstructions from the dev split

Rebuilt on 1 Nov 2026 with `preflight.eval.reconstruct` (Piper voice `en_GB-alan-medium` over generated stills; $0.13 for the three), ingested and transcribed, and each segment re-transcribed as above. Dev items only, none from the test split.

| Item | Turns | Turn scores | Segments | Timing | Words matched |
|---|---|---|---|---|---|
| A24-1239910 | 2 (7.1–19.9 s, 20.5–30.5 s) | 0.499, 0.500 | 4 | word | yes |
| A24-1228813 | 2 (0–4.2 s, 6.1–11.9 s) | 0.495, 0.500 | 2 | word | yes |
| A23-1224570 | 2 (15.3–44.7 s, 44.7–50.2 s) | 0.498, 0.500 | 6 | word | yes |

The first run of A23-1224570 found a fault: a word mixing digits and letters ("53p", "45p") was aligned on its letters alone, so the segment started at the "p" and the spoken number fell outside it, and the false gap split the phrase. Words containing a digit are now left unaligned, like "3000", and take the span between their neighbours; the rerun above has both prices inside their segment. Words written as digits ("12", "3000") were already handled this way.

Correct transcripts score close to 0.50 on every turn here and on the smoke ad, so the score detects a transcript that does not fit the audio; it does not grade alignment quality.

Listened to by: <founder>, <date>
