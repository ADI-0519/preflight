# Flagged lines the ASA never objected to (P70)

On `screen-20261102T014816` (split v2 dev, judge_v5), 149 of the 298 flagged lines on the 25 positive ads matched no claim the ASA cited under a related rule (`unmatched_lines_per_positive_ad`, 149/25). Each of those lines was read against its ad's dev ground truth and given one class. Dev items only (`docs/product-rules.md`, rule 5).

## Classes

| Class | Lines | What it is |
|---|---|---|
| A. Defensible breach the ASA didn't cite | 45 | A real problem in the line that the ruling did not take up: claims of suitability or dosing for children, testimonials of results, "clinically backed", "3x more absorption", general well-being lines with no specific claim beside them |
| B. Register wording flagged anyway | 0 | None. No line flagged authorised wording or wording within what the register authorises |
| C. A description read as a claim | 8 | Symptom stories ("I kept my bladder problems a secret for years"), ingredient lists, the product name |
| D. Scoring miss | 48 | The line carries a ground-truth claim the matcher did not find (below) |
| E1. The ASA's claim under an unrelated rule | 26 | The line is the ASA's claim, but every rule the judge cited is unrelated to the ruling's rules |
| E2. A picture described as a claim | 20 | Implied claims extraction wrote from images ("A smiling woman holding the product suggests..."); the ground truth quotes ad wording only |
| E3. No claim | 2 | "Or...", "My first week was crazy good" |

Scoring misses (D) split into 37 fragments of a longer ground-truth claim ("Relieves stiffness" against "Relieves soreness, stiffness, and discomfort"), 5 lines that quote a whole claim but run past the length limit, 2 where the reconstruction replaced the product name, 2 hashtags written as one word ("#ultimatehangovercure"), 1 inflection ("improving" against "improved") and 1 spelling ("energized" against "energised").

Twenty-two of the 26 E1 lines sit in four ads. In A24-1241023 and A24-1241022 (menopause supplements), the ASA ruled every claim, energy, bloating and weight included, as a claim to treat a condition (15.6, 15.6.2); judge_v5 cited them as health claims (15.1, 15.1.1, 15.7). In A23-1224570, the ASA cited "Dump the Junk" and its kin as denigration (3.41); the judge cited 15.6.5. In A23-1216841 the ASA cited "advanced bladder support" under 15.2, the judge under 15.1.1. The remaining four are single cases.

## Scoring fix

`eval/score.py` now counts a flagged line as matched when, under a related rule, it quotes a ground-truth claim at any length or is a piece of one (at least two words, 80% of them found in order in the claim). Claim recall keeps the tight match, so a fragment or an over-long quote still does not count as a catch. The fix frees 35 of the 149 lines: 33 scoring misses and two near-quotes classed A. The 15 scoring misses left (9 fragments padded with other words, plus the name, hashtag, inflection and spelling cases) are left as they are.

Both baselines were rescored with no model calls; claim recall is unchanged.

| Run | Judge | `claim_recall_carried` | `_by_chance` | `_weighted` | `unmatched_lines_per_positive_ad` |
|---|---|---|---|---|---|
| `screen-20261102T014816-rescored-20261102T163113` | judge_v5 | 178/238 | 91.1/238 | 115.1/238 | 114/25 (was 149) |
| `screen-20261102T144143-rescored-20261102T163114` | judge_v6 | 167/238 | 60.0/238 | 161.9/238 | 116/25 (was 152) |

The second rescore is registered at `d9f9759-dirty` because the first had just added its rows to `results/runs.csv`; both ran on the code at `d9f9759`.

For P70's comparison, the judge_v6 baseline is now 116/25 unmatched lines.

## Evidence for judge_v7

The classes above describe judge_v5. Neither A nor D is noise: A holds breaches a reviewer should see, and D was the scorer's fault. Of what remains, E1 (26) is the largest class the judge controls: the judge flags the ASA's own claims but cites the wrong rule family. E2 (20) starts in claim extraction, which writes implied claims from pictures; a judge prompt can only decline to flag them. C (8) and E3 (2) are small.

## Line IDs

IDs are `<item>/<claim>` in `data/work/runs/screen-20261102T014816/` (the screening is `<run>-<item>-reconstruction`).

- **A (45):** A24-1243213/6, /16, /30, /33, /34; G24-1248968/0, /15; A24-1239910/19; A24-1239908/5; A24-1239905/6, /26, /27, /42; A24-1239904/39; A24-1241337/7, /9, /11, /19; A24-1231792/4; A24-1229687/9; A24-1241022/30, /40, /51, /61; G24-1241706/5, /10; A24-1228813/4, /8; A23-1224570/0, /1, /10, /17, /20, /27; A23-1216841/18, /22, /23; A23-1196136/0, /5, /30, /34, /42, /43, /44, /45
- **C (8):** A24-1239905/33; A24-1239904/25, /46; A24-1238193/6; A24-1241024/20; A24-1241022/43, /47; A23-1216841/24
- **D, fragment (37):** G24-1248968/19, /20; A24-1239907/1, /2, /13; A24-1239905/22, /25, /37, /64, /65; A24-1241337/15, /16; A24-1238193/5; A24-1231792/7, /8, /9; A24-1241024/0, /3, /4, /5, /7, /8, /9, /10, /11, /12, /17, /18; G24-1241706/8, /19, /22, /25, /26, /29, /30; G23-1215538/13, /14
- **D, length (5):** A24-1241017/0; A24-1239905/62; A24-1239904/42; A24-1238193/3; A24-1241022/22
- **D, other (6):** name A24-1238193/1, A24-1228813/3; hashtag A24-1228813/0, /1; inflection A24-1239905/38; spelling A24-1239905/39
- **E1 (26):** A24-1239910/4; A24-1241023/9, /15, /16, /19, /20, /22, /25, /26; A24-1241024/14; A24-1241022/16, /18, /32, /67, /71, /76, /77; A23-1224570/5, /6, /8, /9, /24; A23-1216841/0, /4; A23-1196136/9; A23-1191380/1
- **E2 (20):** A24-1243213/42, /43; A24-1240828/11; A24-1239910/33; A24-1239905/66; A24-1241337/21; A24-1238193/0, /23; A24-1229687/10; A24-1241024/21; A24-1241022/82; G24-1241706/31, /32; A24-1228813/11, /12, /13; A23-1224570/28; A23-1202159/21, /22; A23-1196136/46
- **E3 (2):** A24-1241022/80; A24-1228813/10

One person (NEESAY) assigned these classes. P33 step 3's two-person labels of 20 unmatched lines measure how far a second reader agrees.

## judge_v7

`prompts/judge_v7.txt` adds five lines of guidance to judge_v6, each aimed at a class above:

- E1: an ad names a condition anywhere (headline, product name, an expert's title, a hashtag, a testimonial) presents the product for it; menopause counts, and in such an ad claims about energy, mood, sleep, weight, bloating or hormones cite 15.6 and 15.6.2 (the CAP pack's breach text for 15.6.2 names "menopause symptoms framed as a condition"). Claims to repair or regrow damaged tissue are claims to treat a condition. Telling consumers to drop rival products cites 3.41, with 15.6.5 kept for saying other foods are unsafe or inadequate. A claim that a product supports a body system, naming no function, is a general claim under 15.2.
- E2: a picture description is no issue when the ad's words make the same claim.
- Precedents: a ruling is cited only for a claim about the same condition, body function or ingredient; most claims cite none.

Class A guidance is unchanged. The prompt holds no ruling ID and no three-word phrase from a ground-truth claim (`tests/test_claims.py`).

| Run | Judge | `claim_recall_carried` | `_by_chance` | `_weighted` | unmatched lines | negatives flagged | ruling citations (top six) |
|---|---|---|---|---|---|---|---|
| `screen-20261102T144143-rescored-20261102T163114` | judge_v6 | 167/238 | 60.0/238 | 161.9/238 | 116/25 | 0/15 | 485 (347) |
| `screen-20261102T172225` | judge_v7 draft | 193/238 | 56.6/238 | 184.7/238 | 77/25 | 0/15 | 283 (216) |
| `screen-20261102T173132` | judge_v7 | 192/238 | 55.3/238 | 185.0/238 | 81/25 | 0/15 | 315 (220) |

Both judge_v7 runs used turn timing (`--no-align`), as the judge_v6 run did, so every stage but the check came from the cache. Carried recall rose by 25 claims while recall by chance fell, so the gain does not come from citing more rules; rule precision rose from 446/594 to 494/543. The two judge_v7 runs agree within one claim. About 20 of the 25 extra claims come from one menopause ad (A24-1241022), and 4 from the joint ad (G24-1241706), so the size of the gain on another split depends on how many of its ads are framed around a condition.

Blind read of cited rulings: 40 citations sampled from each run were shuffled together and graded by a reader who saw only the claim and the start of the ruling's ad description (2 similar claim, 1 same broad area, 0 unrelated). judge_v6 scored 49 of 80 with 3 unrelated citations; judge_v7 scored 52 of 80 with 1. The difference in the share is within what 40 citations can resolve, but judge_v7 also cites rulings 315 times against 485, so it makes fewer unrelated citations overall. Six rulings still carry 70% of citations, since claims in one ad cite the same on-topic ruling.
