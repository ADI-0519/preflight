# Keyword baseline (P32)

Measured 2 Nov 2026 on split v2 dev, near-miss items included. The figures come from `baseline-20261102T174026` in `results/runs.csv`; per-item rows are in `results/runs/baseline-20261102T174026.csv`.

## What it does

`uv run python -m preflight.eval.baseline --split v2 --part dev` screens each item with no model calls and scores it with the same harness as the model runs (`preflight.eval.score`). It flags a sentence when:

- it names a register substance (found by the checker's shortlist matcher) without the wording of an authorised entry for that substance: 15.1 and 15.1.1;
- it names a term from a fixed list of diseases, conditions, symptoms and cure words (`DISEASE_TERMS`): 15.6 and 15.6.2.

**It reads the text as written, not as heard or seen.** For a ruling item that is the reconstruction's shot list (on-screen lines and voiceover); for a team item, the ad's own lines. The models read the rendered media through OCR and transcription, so the baseline is spared their errors. If anything, that flatters the baseline.

## Results on split v2 dev

| | Keyword baseline | Models (judge_v6, end to end) |
|---|---|---|
| Ruling ads with a correct flag | 14 of 25 | 25 of 25 (`screen-20261102T141820`, `142908`, `144143`) |
| Ruling claims with a matching rule | 21 of 250 | 156 to 190 of 250 (same three runs) |
| Clean team ads flagged | 14 of 15 | 0 of 15 (same three runs) |
| Near-miss lines caught | 9 of 10 | 9 of 10 (`screen-20261102T170916`) |
| Clean lines flagged in near-miss ads | 16 of 66 | 1 of 66 (same run) |
| Register wording suggested on near-miss lines | 0 of 10 | 7 of 10 (same run) |

- **What the models add is recall on real ads, and silence on clean ones.** The baseline finds a breach in 14 of 25 ruled ads and under a tenth of their breaching claims, while flagging 14 of the 15 compliant ads, mostly for naming a product ("Vitamin C effervescent tablets").
- **Near-miss lines are easy for it**, because the inserted lines name a substance with unauthorised wording or a disease term, which is what it looks for. It pays for that with 16 false alarms in the same ads.
- It never suggests wording.

## Caveats

- **The disease list was written after the split's items and the near-miss lines had been read**, so it may suit them better than unseen ads. It holds general medical vocabulary only, and no ruling's wording.
- **No test run yet.** Split v2 is not frozen: the test near-miss items (P65) and the P60 checks are still to come, and the test part runs once. Run `--part test` from a clean tree after v2 is frozen.
- Substance names shorter than four letters (DHA, EPA) are not matched, as in the checker's shortlist.
