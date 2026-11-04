# claims_v5 and judge_v8 (P66)

Two prompt candidates measured on split v2 dev on 3 Nov 2026. Together they catch 210 of 248 carried claims against 204, cut unmatched lines from 89 to 67 on the 35 positive ads, and raise recall on claims split across cuts or cards from 95 to 114 of 232. The founders signed both off on 3 Nov 2026 and they are now the defaults. Dev only (`docs/product-rules.md`, rule 5).

## Why

Two losses remained on `screen-20261102T210524` (claims_v3, judge_v7):

- **Claims shown in pieces.** When an ad splits a claim across scenes, cards or lines, extraction quotes the pieces apart, and the judge never sees the claim whole. On the `split_cuts` stress set this lost 87 of 104 claims (`docs/notes/stress-set.md`).
- **Rules from the wrong family.** Of the 45 carried claims the plain run missed, 17 were flagged under a rule unrelated to the ASA's, and 15 were flagged with a matching rule but quoted only inside a sentence too long to score. Eleven of the 17 are energy, focus, memory and thinking claims in ads framed around ADHD or brain fog, where judge_v7 cites 15.6 alone and the ASA ruled them unauthorised health claims under 15.1 and 15.1.1.

## What changed

**claims_v5** keeps every line of claims_v3 and adds five at the end of the quoting paragraph:

- a long sentence, spoken or shown, gets one short entry for each claim inside it, starting at the words that make the claim;
- texts or segments that follow each other in time and read as one sentence are quoted joined, in the ad's words and order, citing every piece;
- pieces are joined only when the later one continues the earlier one's sentence;
- each piece that is a claim on its own is still listed;
- a joined claim holds only words the ad shows or says.

claims_v4 is the same without the first line's last clause and "or shown". On plain dev it lost list items to the length limit by quoting each with the whole sentence before the list, which the first line of claims_v5 corrects.

**judge_v8** changes three lines of judge_v7:

- outside menopause, a claim to boost energy, focus, concentration, memory or thinking stays a 15.1 and 15.1.1 health claim in an ad framed around a condition, and is also a 15.6 and 15.6.2 claim only when its own words name the condition or say it treats it;
- a claim of approval by a body may cite 3.1 with 3.52 beside a Section 15 rule;
- in a menopause ad, "feeling better" and "seeing a difference" are claims to relieve its symptoms, as energy and sleep already were.

Both prompts were written from the CAP rule pack and the labelling rule; the synthetic example in claims_v5 is invented. `tests/test_claims.py` now checks every claims and judge prompt against the ground truth of split v2 as well as v1.

## Results

All runs use turn timing (`--no-align`) and vote over three judge samples, so they compare with the voting baselines. Intervals are 95%, bootstrapped over ads.

| Run | Claims | Judge | Carried caught | By chance | Weighted | Rule precision | Unmatched lines | Negatives flagged |
|---|---|---|---|---|---|---|---|---|
| `screen-20261102T211550` | v3 | v7 | 204/248 [0.769, 0.873] | 58.7 | 198.5 | 523/573 | 89/35 | 0/15 |
| `screen-20261103T030648` | v3 | v8 | 211/248 [0.805, 0.892] | 59.9 | 204.1 | 545/590 | 87/35 | 0/15 |
| `screen-20261103T032900` | v5 | v8 | 210/248 [0.802, 0.886] | 62.2 | 203.6 | 583/625 | 67/35 | 0/15 |

Near-miss items stay at 10/10 caught with 1 of 65 clean lines flagged in all three runs; wording on eligible lines is 6/10, 8/10 and 7/10.

| Run (`split_cuts`) | Claims | Judge | Carried caught | Ads caught | Unmatched lines |
|---|---|---|---|---|---|
| `stress-split_cuts-20261103T015225` | v3 | v7 | 95/232 [0.298, 0.552] | 22/24 | 122/24 |
| `stress-split_cuts-20261103T032859` | v3 | v8 | 96/232 [0.300, 0.550] | 22/24 | 124/24 |
| `stress-split_cuts-20261103T032906` | v5 | v8 | 114/232 [0.388, 0.622] | 23/24 | 129/24 |

Single-sample runs of claims_v4 with judge_v7 are registered as `screen-20261103T024949` (201/248 against 203 for `screen-20261102T210524`) and `stress-split_cuts-20261103T024948` (100/232 against 94).

What the runs show:

- **judge_v8 gains are the claims it was written for.** Against the judge_v7 voting run it gains 8 claims and loses 1 (`compare-20261103T032009`): five focus and memory claims in one ADHD-framed ad (A24-1239904), one approval claim, one menopause "see a difference" claim and one other. Recall by chance rises by 1.2 claims, so the gain does not come from citing more rules. It does not change recall on split claims (95 against 96).
- **claims_v5 rejoins split claims.** Of the 155 `split_cuts` claims that reach the screening only in pieces, extracted claims quote 70 whole with claims_v5 against 53 with claims_v3, and 65 of those are flagged with a matching rule against 48. On plain dev it holds recall (210 against 211, within the 8-claim spread between voting runs) and removes 20 unmatched lines.
- **Unmatched lines on `split_cuts` rose from 124 to 129** with claims_v5, as joined passages add flagged lines alongside their pieces.

## Limits

- Most of judge_v8's gain sits in one ad, as most of judge_v7's sat in one menopause ad (`docs/notes/noise-lines.md`), so its size on the test split depends on how many test ads are framed around a condition other than menopause.
- The `split_cuts` render cuts a line holding two claims more than once and puts alternate pieces on each scene (`preflight.eval.stress.split_line`). For 32 of the 104 claims lost on `stress-split_cuts-20261103T013804`, the pieces reach the screen out of order or glued to another claim's piece, which no real ad does and no prompt can rejoin. The other 69 are cut into two pieces in reading order and 3 were lost at other steps. The `split_cuts` figures above understate recall on real split ads by an amount this set cannot measure until the render keeps each claim's pieces in order.
- With one judge sample, judge_v8 broke its output contract on one item (N02: a `no_issue` verdict citing sources), which fails the check stage. Voting, the default since P66, lets that sample abstain.

## Open questions

- **Sign-off and defaults (done 3 Nov).** Both prompts are signed off and are the defaults in `preflight.claims` and `preflight.check`. The replay fixtures in `tests/fixtures/models/` gained the new prompts' answers for the fixture clip (one claims call, three judge samples), and the replay screening, API and web tests pass on them.
- **The `split_cuts` render.** Whether to fix `split_line` so each claim's pieces stay in reading order, and re-render and rescreen the set. That changes a measurement, so the stress figures in `docs/notes/stress-set.md` would be quoted from the new runs.
