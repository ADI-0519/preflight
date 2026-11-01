# Checker (P27)

Measured 1 Nov 2026 on dev split v1. Every number below comes from a run registered in `results/runs.csv`; per-item rows are in `results/runs/<run_id>.csv`.

**Integration note (1 Nov):** The measurements below predate the adi-branch integration safeguards. The integrated parser also validates cached/replayed verdicts locally, restricts register and on-hold citations and suggested wording to candidates for the individual claim, and rejects sources or wording on a `no_issue` verdict. Invalid decisions fail the check stage rather than silently losing a flag or suggestion. Candidate matching alone does not establish semantic suitability or fulfilment of a register entry's conditions. No new live measurement was made for these changes; do not attribute the numbers below to the integrated version.

## What the stage does

`preflight.check.check(screening, spark, precedents)` takes a screening with claims and returns it with flags and a `check` stage record. It makes one Muse Spark call per ad (Standard mode, strict JSON schema, text only) and runs `verify_sources` on the result before returning it.

The call carries four lists:

- **The ad's claims**, with the transcript, on-screen text and tracks they came from.
- **A register and on-hold shortlist** (`preflight.check.shortlist`). Each claim's substance, and every register substance named in a claim's text, is matched by whole-word phrase, a parenthetical name or a short alias table. All matching authorised entries are kept; non-authorised and on-hold matches are capped at 30 per substance. No model call is made per entry. On the dev screenings the shortlist runs from 0 to 127 register entries per ad.
- **The screenable rules of the CAP rule pack** (41 rules, `data/snapshots/cap-2026-10-31.yaml`).
- **The three past rulings** that score highest under BM25 against the ad's claim texts (`preflight.check.precedents`), each with its ad description and the opening of its assessment.

The model returns one verdict per claim: `possible_breach`, `on_hold` or `no_issue`, with the rules, register entries, on-hold entries and rulings it cites and a short reason. The schema limits every citation to an enum of what the call listed, and the parser raises unless every claim is judged exactly once, since an unjudged claim would read as no issue. The issue's "needs a person" verdict was dropped: the schema has no such flag kind, and every flag is for a person to decide (`docs/product-rules.md`, rule 4).

Suggested wording follows rule 2. The model may name an authorised shortlist entry; the wording is then copied from the register by `SuggestedWording.from_entry`. A flag that cites no section 15 rule and is not on hold never gets a suggestion, so misleading and comparative claims under section 3 get none. The schema rejects a breach flag that cites nothing, or only the on-hold list (rule 3).

## The precedent index

The rulings corpus was widened on 1 Nov, because split v1 uses 74 of the 77 rulings in the P13 corpus and the index would otherwise hold three. The P13 fetcher ran again over formal rulings published 31 Oct 2019 to 30 Oct 2023, under the same scope test and 10 s spacing (`docs/source-terms.md`): 63 candidates, all downloaded. The snapshot `data/snapshots/rulings-2026-11-01.jsonl` holds 112 in-scope rulings, metadata only.

Rule 5 keeps every split v1 ruling out of the index. By founders' decision of 1 Nov it also keeps out every other ruling on an advertiser that appears in the split, since an older ruling on the same brand can describe nearly the same ad (`docs/notes/decisions.md`). `PrecedentIndex` refuses to build if given either kind, and a test checks both. Of the 38 in-scope rulings outside the split, 5 share a split advertiser, which leaves **33 rulings** in the index: 30 from 2022 and 2023, 2 from 2021 and 1 from 2026.

## How it is scored

`uv run python -m preflight.eval.check_recall --rulings 2026-11-01` judges the claims of the saved P26 dev screenings (`claims-20261101T023641`, prompt `claims_v3` at high effort), so extraction is not rerun. A ground-truth claim counts as caught when a flagged claim matches it under P26's length-limited match and the flag cites one of its rules, or a rule above or below it (15.6 matches 15.6.2). `claim_recall_any_rule` drops the rule condition.

The five team-written dev negatives have no rendered media. Their on-screen lines and voiceover sentences are judged directly as claims, so their false-alarm figures measure the judge alone and are named `*_judge_only`.

## Results

| Run | Prompt | Ads with a correct flag | Claims caught with a matching rule | Claims flagged, any rule | Flags per positive ad | Team negatives flagged (judge only) | Cost per item |
|---|---|---|---|---|---|---|---|
| check-20261101T033145 | judge_v1 | 24 of 25 | 154 of 250 | 198 of 250 | 23 | 0 of 5 | $0.070 |
| check-20261101T033858 | judge_v2 | 24 of 25 | 183 of 250 | 200 of 250 | 24 | 0 of 5 | $0.068 |
| **check-20261101T035641** | **judge_v3** | **24 of 25** | **182 of 250** | **198 of 250** | **23** | **0 of 5** | **$0.069** |

All three runs used high reasoning effort and took about 45 s of model time per item. All ran on uncommitted code, so their SHAs carry `-dirty`. Each ran once, so a difference of a few claims is within run-to-run variation; the step from v1 to v2 is not, and v2 and v3 catch the same claims.

The default is v3. It catches as many claims as v2 with tighter citations: 3.3 CAP rules per flag against 4.5 (at most 8 against 12), and 500 ruling citations against 709. Because the matching-rule figure counts a hit when any cited rule matches, citing fewer rules can only lower it; it fell by one claim.

Extraction bounds every figure: P26 found 209 of the 250 claims, so 209 is the most the checker can catch from these screenings. judge_v3 flags 198 of those 209 and cites a matching rule on 182.

## Prompt versions

The judge prompt follows the P26 authorship rule: it is written from the CAP rule pack and the product rules only, tuned on dev only, and a test fails if any split ruling ID or ground-truth claim of three or more words appears in a `prompts/judge_*` file.

- **v1** states the register test, the on-hold handling, 15.2, 15.6.2 and section 3, and asks for a verdict on every claim. It flagged 44 claims only under rules the ruling did not cite. In a breakdown of 40 of them by rule, 27 were disease claims under 15.6.2 that it cited only as unauthorised health claims (15.1.1, 15.7). These were symptom claims ("bloating", "energy", "sleep") in ads aimed at a condition such as menopause. Its reasons also paraphrased the claims in odd words, because v1 told it never to reword a claim.
- **v2** adds that a claim to relieve the symptoms of a condition the ad targets is a claim to treat that condition, also in testimonials and claims that do not name it. It asks for 15.6 with any sub-rule, and asks the reasons to quote the claim exactly while never proposing wording.
- **v3** asks for the rules the claim's own words breach, leaving out problems that lie elsewhere in the ad, and for a ruling only when it found the same kind of claim in breach under a cited rule. A read of 20 v2 flags found up to 10 rules on one claim, and rulings were cited on claims they had nothing in common with.

## Checks beyond the registered runs

Three checks on the dev output were read rather than registered, so they carry no figure for the README or the video.

- **On-hold and suggested wording (v2).** Every on-hold citation named the right substance (ashwagandha as *Withania somnifera*, reishi, curcumin). Claims that were also disease claims became possible breaches citing the on-hold entry, as the rule pack requires. All five suggestions were authorised magnesium wording, copied exactly, on magnesium claims; two sit on fear or deficiency claims (15.6.4, 15.8), where the suggested claim answers only part of the problem.
- **Precedent fit (v2).** 690 of 709 ruling citations shared a CAP rule family with their flag, but only 14 rulings were cited, and in a sample of ten pairs about half were about a similar claim. Retrieval is per ad, so the judge chooses from the same three rulings for every claim. v3 cut the citations by 29% at the same recall.
- **Over-reading on compliant ads.** Six invented ads, each an authorised claim copied exactly plus ordinary marketing lines (a general well-being line beside the specific claim, a pack size, a taste), were judged outside the split. v2 flagged two of them and v3 one, each time for a relaxation line ("Relax and recharge") cited as an unauthorised specific claim under 15.1.1, which is a call for a person. Neither cited 15.6.2, and an authorised vitamin C claim mentioning oxidative stress was left alone.

## Caveats

- **The disease reading needs checking on real compliant ads.** In condition-targeted dev ads, v2 and v3 call stress and calm claims disease treatment. The six-ad probe found no such reading outside a condition-targeted ad, but the team negatives use only register wording and six invented ads are not a false-alarm rate; P33's error analysis should look at it.
- **The judge flags about 24 claims per positive ad**, since P26 lists overlapping phrases and the claims inside them. The flag count overstates the number of distinct problems.
- These are reconstructions, judged from the claims P26 extracted. The end-to-end figures on the test split (P33) are the ones to report.
- **Precedents are thin.** v3 still cites a ruling on 374 of its 563 flags, from an index of 33. Retrieving per claim, or a larger corpus, would fit them better.

## For the founders

- **Prompt sign-off.** Neesay or ADI-0519 reviews `prompts/judge_v3.txt` before it runs on the test split.
- **A read of the flags.** Neesay or ADI-0519 reads a sample of v3's dev flags (`data/work/runs/check-20261101T035641/`), since the checks above were made while the prompt was being tuned.
- **Precedent corpus.** 33 rulings is small. Rulings from before Oct 2019 or from other topics would add more, at about 10 s per page.
