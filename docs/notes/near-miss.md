# Near-miss items (P65)

Measured 2 Nov 2026 on split v2 dev, with judge_v7 (`screen-20261102T182225`) and earlier with judge_v6 (`screen-20261102T170916`). Both runs are in `results/runs.csv`, with per-item rows in `results/runs/<run>.csv`.

## What they are

A near-miss item is a compliant team ad with one breaching line put in. It is the case a reviewer meets most: an ad that is mostly fine with one bad line. The ten dev items N01 to N10 are built on the dev negatives T16 to T25, one each.

- **Breach lines** are in `eval/near_miss/dev.yaml`, each with its substance and CAP rules. Most overstate the ad's own authorised claim ("Vitamin C supercharges your immune system", where the register allows "contributes to the normal function of the immune system"). Five are disease claims.
- **`scripts/near_miss.py eval/near_miss/dev.yaml`** writes `eval/items/team/N*.yaml`, which is the base ad plus `base`, `inserted` and `substance`, and the item's ground truth: a positive with the one inserted claim, and `checked_by` empty. An image ad gets the line on screen just before the food supplement statement; a video ad gets it at the end of the voiceover.
- **Rendering:** `preflight.eval.team_media.build_team`, as for the other team ads.
- **Test items** come from a test breach file run through the same script. Its author never sees the judge prompt or its tuning, and whoever writes or tunes the judge prompt never reads the file (rule 5).

## Metrics

Registered for the near-miss items in a run (`preflight.eval.score.near_miss`), and with `_judge_only` names by `check_recall`:

- `near_miss_caught`: the inserted line is flagged with one of its rules, per ad, with an exact interval.
- `clean_lines_flagged`: of the ad's other lines, all compliant, the share a flag lands on. A flag that also lands on the inserted line does not count against the clean lines.
- `wording_on_eligible`: of the items whose inserted line is about a substance the register authorises, the share where a flag on that line suggests an authorised entry for that substance, or for any substance the line names. N07's "Calcium and vitamin D prevent osteoporosis" can take calcium's wording, vitamin D's, or the joint entry on bone mineral loss. All ten dev items are eligible.

## Results (end to end)

Intervals are exact 95% bounds over ads, or over lines for `clean_lines_flagged`; lines of one ad are not independent, so that interval is too narrow.

| Metric | judge_v7 | judge_v6 |
|---|---|---|
| near_miss_caught | 10 of 10 [0.69, 1.00] | 9 of 10 [0.56, 1.00] |
| clean_lines_flagged | 1 of 66 [0.00, 0.05] | 1 of 66 [0.00, 0.05] |
| wording_on_eligible | 6 of 10 [0.26, 0.88] | 7 of 10 [0.35, 0.93] |
| flags per ad | 1.8 | 1.8 |
| cost for 10 ads | $1.05 | $0.99 |

The judge_v7 run used `--no-align`, as the judge_v7 dev runs did, and media rendered again from the same item files.

- **judge_v7 caught N03.** Its "Magnesium stops muscle cramps for good" is labelled a disease claim (15.6, 15.6.2). judge_v6 flagged it as an overstated health claim (15.1, 15.1.1, 15.7) and missed; judge_v7 cited 15.6.2. Cramps are a symptom, so the label is still for the founder who checks N03 to settle.
- **The one clean line flagged is a transcription error in both runs.** In N06 the voiceover's "Zinc contributes to the normal function of the immune system" was heard as "sync contributes...", which no longer matches the register.
- **judge_v7 suggests no wording on four of the five disease claims:** N02 (vitamin D against colds and flu), N03, N08 (vitamin C for anxiety) and N10 (DHA for damaged eyesight). On N07 it suggests the joint calcium and vitamin D entry on bone mineral loss, which the earlier exact-substance match would have scored as a miss. Every overstated claim gets its substance's wording.
- **judge_v6 suggested no credited wording on N02, N07 and N08.** That run was scored before the match took every substance the line names, so N07 may be a scoring miss there.

## Caveats

- The breach lines and base ads were written by the team, so the figures describe our copy, not customer ads.
- The dev breach lines were drafted for Neesay with an AI assistant. NEESAY checks them and sets `checked_by`.
- The base ads T16 to T25 still await their own founder check (P60).
- N01 to N10 take v2 dev from 40 items to 50 (35 positives). Pooled dev figures from earlier v2 runs cover 40 items and do not compare directly with whole-dev runs from here on.
