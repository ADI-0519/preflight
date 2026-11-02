# Keyword baseline (P32)

Measured 2 Nov 2026 on split v2 dev with `keyword-baseline-v2`. The figures come from `baseline-20261102T185756` (ruling and negative items), `baseline-20261102T185759` (near-miss items) and `baseline-20261102T185804` (the whole part) in `results/runs.csv`; per-item rows are in `results/runs/`. All three ran the code at `0828a54`; the later two read `-dirty` only because the run before them had added its rows to `runs.csv`.

## What it does

`uv run python -m preflight.eval.baseline --split v2 --part dev` screens each item with no model calls and scores it with the same harness as the model runs (`preflight.eval.score`). `--only` takes item IDs, as in `preflight.eval.run`. It flags a sentence when:

- it names a register substance (found by the checker's shortlist matcher) and a benefit (`CLAIM_TERMS`: verbs such as "supports" and body functions such as "immune"), without the wording of an authorised entry for that substance: 15.1 and 15.1.1;
- it names a term from a fixed list of diseases, conditions, symptoms and cure words (`DISEASE_TERMS`): 15.6 and 15.6.2. Words inside an authorised wording are not checked, since some name a condition ("normal thyroid function").

**It reads the text as written, not as heard or seen.** For a ruling item that is the reconstruction's shot list (on-screen lines and voiceover); for a team item, the ad's own lines. The models read the rendered media through OCR and transcription, so the baseline is spared their errors. If anything, that flatters the baseline.

## Results on split v2 dev

| | Keyword baseline | Models (judge_v7, end to end) |
|---|---|---|
| Ruling ads with a correct flag | 14 of 25 | 25 of 25 (`screen-20261102T172225`, `173132`) |
| Ruling claims with a matching rule | 20 of 250 | 192 to 193 of 250 (same two runs) |
| Clean team ads flagged | 0 of 15 | 0 of 15 (same two runs) |
| Near-miss lines caught | 8 of 10 | 10 of 10 (`screen-20261102T182225`) |
| Clean lines flagged in near-miss ads | 0 of 66 | 1 of 66 (same run) |
| Register wording suggested on near-miss lines | 0 of 10 | 6 of 10 (same run) |

- **What the models add is recall on real ads.** The baseline finds a breach in 14 of 25 ruled ads and under a tenth of their breaching claims; the models find all 25 ads and about three quarters of the claims.
- **False alarms do not separate them.** On clean ads and on the clean lines of near-miss ads the baseline is as quiet as the models.
- **Near-miss lines are mostly easy for it**, because an inserted line names a substance with a benefit or a disease term, which is what it looks for. It misses "Zinc doubles your body's natural defences" (no benefit word) and the DHA line (too short a name).
- It never suggests wording.

The first version (`keyword-baseline-v1`, `baseline-20261102T174026`) flagged any sentence naming a substance without an authorised wording. It flagged 14 of the 15 clean ads and 16 of the 66 clean lines, mostly product names ("Vitamin C effervescent tablets") and lines the matcher read as a substance ("with water", "raspberry flavour").

## Caveats

- **Both word lists were written after the split's dev items and the near-miss lines had been read**, so they may suit them better than unseen ads. They hold general vocabulary only, and no ruling's wording.
- **No test run yet.** Split v2 is not frozen: the test near-miss items (P65) and the P60 checks are still to come, and the test part runs once. Run `--part test` from a clean tree after v2 is frozen.
- Substance names shorter than four letters (DHA, EPA) are not matched, as in the checker's shortlist.
