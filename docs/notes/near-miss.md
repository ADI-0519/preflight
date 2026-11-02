# Near-miss items (P65)

Measured 2 Nov 2026 on split v2 dev. The numbers come from `screen-20261102T170916` in `results/runs.csv`; per-item rows are in `results/runs/screen-20261102T170916.csv`.

## What they are

A near-miss item is a compliant team ad with one breaching line put in. It is the case a reviewer meets most: an ad that is mostly fine with one bad line. The ten dev items N01 to N10 are built on the dev negatives T16 to T25, one each.

- **Breach lines** are in `eval/near_miss/dev.yaml`, each with its substance and CAP rules. Most overstate the ad's own authorised claim ("Vitamin C supercharges your immune system", where the register allows "contributes to the normal function of the immune system"). Five are disease claims.
- **`scripts/near_miss.py eval/near_miss/dev.yaml`** writes `eval/items/team/N*.yaml`, which is the base ad plus `base`, `inserted` and `substance`, and the item's ground truth: a positive with the one inserted claim, and `checked_by` empty. An image ad gets the line on screen before the food supplement statement; a video ad gets it at the end of the voiceover.
- **Rendering:** `preflight.eval.team_media.build_team`, as for the other team ads.
- **Test items** come from a test breach file written by NEESAY and run through the same script. Whoever writes or tunes the judge prompt never reads it (rule 5).

## Metrics

Registered for the near-miss items in a run (`preflight.eval.score.near_miss`), and with `_judge_only` names by `check_recall`:

- `near_miss_caught`: the inserted line is flagged with one of its rules, per ad, with an exact interval.
- `clean_lines_flagged`: of the ad's other lines, all compliant, the share a flag lands on. A flag that also lands on the inserted line does not count against the clean lines.
- `wording_on_eligible`: of the items whose inserted line is about a substance the register authorises, the share where a flag on that line suggests an authorised entry for that substance. All ten dev items are eligible.

## Results (judge_v6, end to end)

| Metric | Value |
|---|---|
| near_miss_caught | 9 of 10 [0.56, 1.00] |
| clean_lines_flagged | 1 of 66 [0.00, 0.05] |
| wording_on_eligible | 7 of 10 [0.35, 0.93] |
| flags per ad | 1.8 |
| cost | $0.99 for 10 ads |

- **The miss is a labelling question.** N03's "Magnesium stops muscle cramps for good" is labelled a disease claim (15.6, 15.6.2) and was flagged as an overstated health claim (15.1, 15.1.1, 15.7). Cramps are a symptom, but the judge's reading is arguable; the founder who checks N03 should settle the label.
- **The one clean line flagged is a transcription error.** In N06 the voiceover's "Zinc contributes to the normal function of the immune system" was heard as "sync contributes...", which no longer matches the register.
- **No wording was suggested** on N02 and N08 (vitamin D against colds and flu, vitamin C for anxiety), both disease claims. The other eight flags on the inserted line suggest the substance's authorised wording.

## Caveats

- The breach lines and base ads were written by the team, so the figures describe our copy, not customer ads.
- The dev breach lines were drafted for Neesay with an AI assistant. NEESAY checks them and sets `checked_by`.
- The base ads T16 to T25 still await their own founder check (P60).
