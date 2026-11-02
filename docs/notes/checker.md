# Checker (P27)

Measured 1 Nov 2026 on dev split v1. Every number below comes from a run registered in `results/runs.csv`; per-item rows are in `results/runs/<run_id>.csv`.

**Since these runs (1 Nov):** judge answers are validated when parsed, including cached ones, and a `no_issue` verdict citing sources is an error. A claim that names a substance keeps only the register and on-hold citations, and the suggested wording, shortlisted for that substance; one naming none may cite any entry shortlisted for the ad. A citation or suggestion that fails this is dropped and the flag kept. The numbers below predate this and need a fresh dev run (`docs/notes/decisions.md`, 1 Nov, P27).

## What the stage does

`preflight.check.check(screening, spark, precedents)` takes a screening with claims and returns it with flags and a `check` stage record. It makes one Muse Spark call per ad (Standard mode, strict JSON schema, text only) and runs `verify_sources` on the result before returning it.

The call carries four lists:

- **The ad's claims**, with the transcript, on-screen text and tracks they came from.
- **A register and on-hold shortlist** (`preflight.check.shortlist`). Each claim's substance, and every register substance named in a claim's text, is matched by whole-word phrase, a parenthetical name or a short alias table. All matching authorised entries are kept; non-authorised and on-hold matches are capped at 30 per substance. No model call is made per entry. On the dev screenings the shortlist runs from 0 to 127 register entries per ad.
- **The screenable rules of the CAP rule pack** (43 rules, `data/snapshots/cap-2026-11-01.yaml`). The 2026-11-01 pack adds 3.39 (price comparisons) and 3.41 (denigration) to the 2026-10-31 pack, in the CAP Code's current numbering, read from the section 3 page on 1 Nov 2026.
- **The closest past rulings** under BM25 against each claim's text (`preflight.check.precedents`, up to five per ad in `judge_v4` and `v5`, or three per ad in `judge_v1`–`v3`), each with its ad description and the opening of its assessment.

The model returns one verdict per claim: `possible_breach`, `on_hold` or `no_issue`, with the rules, register entries, on-hold entries and rulings it cites and a short reason (`reason` precedes `verdict` in the output schema so the model writes its reasoning before committing to a verdict). The schema limits every citation to an enum of what the call listed, and the parser raises unless every claim is judged exactly once, since an unjudged claim would read as no issue. The issue's "needs a person" verdict was dropped: the schema has no such flag kind, and every flag is for a person to decide (`docs/product-rules.md`, rule 4).

Suggested wording follows rule 2. The model may name an authorised shortlist entry; the wording is then copied from the register by `SuggestedWording.from_entry`. A flag that cites no section 15 rule and is not on hold never gets a suggestion, so misleading and comparative claims under section 3 get none. The schema rejects a breach flag that cites nothing, or only the on-hold list (rule 3).

## The precedent index

The rulings corpus was widened on 1 Nov, because split v1 uses 74 of the 77 rulings in the P13 corpus and the index would otherwise hold three. The P13 fetcher ran again over formal rulings published 31 Oct 2019 to 30 Oct 2023, under the same scope test and 10 s spacing (`docs/source-terms.md`): 63 candidates, all downloaded. The snapshot `data/snapshots/rulings-2026-11-01.jsonl` holds 112 in-scope rulings, metadata only.

Rule 5 keeps every split v1 ruling out of the index. By founders' decision of 1 Nov it also keeps out every other ruling on an advertiser that appears in the split, since an older ruling on the same brand can describe nearly the same ad (`docs/notes/decisions.md`). `PrecedentIndex` refuses to build if given either kind, and a test checks both. Of the 38 in-scope rulings outside the split, 5 share a split advertiser, which leaves **33 rulings** in the index: 30 from 2022 and 2023, 2 from 2021 and 1 from 2026.

## How it is scored

`uv run python -m preflight.eval.check_recall --claims-run claims-20261101T184413 --cap-rules 2026-11-01 --prompt judge_v5` judges the claims of saved P26 dev screenings, so extraction is not rerun. A ground-truth claim is matched when a flagged claim matches it under P26's length-limited match. Five numbers come from that:

- `claim_recall_any_rule`: the claim is flagged, whatever rules it cites.
- `claim_recall`: the flag cites one of the claim's rules, or a rule above or below it (15.6 matches 15.6.2).
- `claim_recall_exact_rules`: every rule the flag cites is one of the claim's rules, or above or below one. Citing extra rules earns nothing here, so `claim_recall` can no longer be raised by citing many rules at once.
- `rule_precision`: of the CAP rules cited on flags that match a ground-truth claim, the share related to that claim's rules.
- `flags_per_positive_ad`: every flag on the positives, matched or not.

**Rule numbers changed.** CAP renumbered rules 3.39 to 3.43 after some split v1 ads ran. Their rulings cite the earlier numbers: A23-1216841 cites "3.40 (Price Comparisons)", and A23-1224570 and A24-1251814 cite "3.42 (Imitation and Denigration)". In the current Code those are 3.39 and 3.41, while 3.40 is now about who made the product and 3.42 about a rival's reputation. Scoring reads those three rulings' 3.40 and 3.42 as 3.39 and 3.41 (`preflight.eval.score.FORMER_NUMBERS`), and the judge cites from a pack in current numbering. The ground truth is unchanged.

`--rescore RUN_ID` scores a saved run again under the current scoring with no model calls, registering it as `<run_id>-rescored`. `--cache-dir` gives a run a fresh model cache: without it, a repeat run with the same prompt replays the cached answers and measures nothing.

The five team-written dev negatives have no rendered media. Their on-screen lines and voiceover sentences are judged directly as claims, so their false-alarm figures measure the judge alone and are named `*_judge_only`.

## Results

### On the same extracted claims (`claims-20261101T184413`, 211 of 250 ground-truth claims extracted)

| Run | Prompt | Ads with a correct flag | Claims, matching rule | Claims, any rule | Claims, every rule correct | Rule precision | Flags per positive ad | Team negatives flagged | Cost per item |
|---|---|---|---|---|---|---|---|---|---|
| check-20261101T210411 | judge_v3 | 24 of 25 | 166 of 250 | 203 of 250 | 60 of 250 | 358 of 775 (46%) | 23 | 0 of 5 | $0.059 |
| check-20261101T191521-rescored | judge_v4 | 25 of 25 | 208 of 250 | 211 of 250 | 56 of 250 | 573 of 1,254 (46%) | 25 | 0 of 5 | $0.048 |
| check-20261101T210408 | **judge_v5** | 25 of 25 | 194 of 250 | 210 of 250 | 63 of 250 | 523 of 1,162 (45%) | 24 | 0 of 5 | $0.046 |
| check-20261101T210951 | **judge_v5**, repeat with a fresh cache | 25 of 25 | 190 of 250 | 211 of 250 | 63 of 250 | 522 of 1,161 (45%) | 24 | 0 of 5 | $0.050 |

`check-20261101T210914` is a second v5 run that replayed the first run's cached answers; it is registered but is not a repeat. The v3 run used per-ad precedents, as v3 always has. The v4 run used its own rule pack (below) and is rescored under the renumbering; its registered figure of 211 claims with a matching rule counted three price and denigration claims that it cited under 3.40 and 3.42 in their former meaning.

**What the figures show.**

- **Every prompt cites about two rules for each one that applies** (rule precision 45–46%), and only about a quarter of claims get no wrong rule. A flag's rule list is not yet reliable enough to show without a person's read.
- **v5 keeps most of v4's gain over v3** (194 and 190 against 166 claims with a matching rule) without v4's item-specific wording. The 14 to 18 claims between v4 and v5 are what that wording bought on dev, where it was written; it is not expected to carry to test.
- **Run-to-run noise is about ±4 claims** on one repeat. Differences of that size between prompts are not real.
- **Extraction is the ceiling.** 39 of the 250 claims never reach the judge.
- **The judge flags 23 to 25 claims per positive ad** against 10 ground-truth claims, since P26 lists overlapping phrases and the claims inside them. On the 5 register-worded team ads, which no version flags, that is not a false-alarm rate; split v2's negatives are below.

### Negatives that read like real ads (split v2)

Split v2 adds ten dev negatives (T16-T25): flavours, dosing, an offer and general well-being lines beside an authorised claim, every health claim in exact register wording. judge_v5 flags none of them, judged line by line (`check-20261101T232557`) or end to end, with the rendered ads screened through every stage (`screen-20261101T232627`, $0.91 for the ten). Ten ads the team wrote are not a false-alarm rate on real ads.

### Earlier runs (`claims-20261101T023641`, 209 of 250 extracted; CAP pack 2026-10-31; scored before the renumbering)

| Run | Prompt | Ads with a correct flag | Claims, matching rule | Claims, any rule | Flags per positive ad | Team negatives flagged | Cost per item |
|---|---|---|---|---|---|---|---|
| check-20261101T033145 | judge_v1 | 24 of 25 | 154 of 250 | 198 of 250 | 23 | 0 of 5 | $0.070 |
| check-20261101T033858 | judge_v2 | 24 of 25 | 183 of 250 | 200 of 250 | 24 | 0 of 5 | $0.068 |
| check-20261101T035641 | judge_v3 | 24 of 25 | 182 of 250 | 198 of 250 | 23 | 0 of 5 | $0.069 |

These used a different extraction run, and their screenings were not kept, so they cannot be rescored. They are not comparable with the table above: v3 scores 182 here and 166 there.

## Prompt versions

The judge prompt follows the P26 authorship rule: it is written from the CAP rule pack and the product rules only, tuned on dev only, and a test fails if any split ruling ID or ground-truth claim of three or more words appears in a `prompts/judge_*` file.

- **v1** states the register test, the on-hold handling, 15.2, 15.6.2 and section 3, and asks for a verdict on every claim. It flagged 44 claims only under rules the ruling did not cite. In a breakdown of 40 of them by rule, 27 were disease claims under 15.6.2 that it cited only as unauthorised health claims (15.1.1, 15.7). These were symptom claims in ads aimed at a condition such as menopause.
- **v2** adds that a claim to relieve the symptoms of a condition the ad targets is a claim to treat that condition, also in testimonials and claims that do not name it. It asks for 15.6 with any sub-rule, and asks the reasons to quote the claim exactly while never proposing wording.
- **v3** asks for the rules the claim's own words breach, leaving out problems that lie elsewhere in the ad, and for a ruling only when it found the same kind of claim in breach under a cited rule.
- **v4** places the reference material first and the claims and instructions last, puts `reason` before `verdict` in the schema, includes the proposed wording of on-hold entries, retrieves precedents per claim, and adds guidance on nutrition claims, names, deficiency claims, beauty, weight, safety, prices and denigration. **It is not used**, for two reasons:
  - **Its guidance restates particular dev rulings.** Examples: "Mental Health" as a benefit heading, "superstar" ingredients, hair changes from a deficiency, adding the product to a child's drink, a competitor's "complaints or motives", "Doctor" in a product name, "feeling like one's old self again". The evaluation protocol builds prompts with every dev and test ruling excluded (item 4), and the leakage test, which looks for copied claims of three or more words, does not catch reworded lessons.
  - **It was written against a rule pack edited in place.** The 2026-10-31 pack was changed to give 3.40, 3.42, 3.43 and 3.44 their former meanings, so v4 cites 3.40 for price comparisons, which in the current Code is the rule on who made the product. That edit is undone; the 2026-10-31 pack is again as read on 31 Oct and matches the current Code.
- **v5** is v4 with the item-specific wording, the example lists drawn from dev ads and the instructions to cite extra rules "alongside" removed, and 3.40 and 3.42 changed to 3.39 and 3.41. Nothing was added. It was written by someone who has read test-split ground truth (in P14 and P15), so it was made by deletion only, which can carry nothing from the test split into the prompt (rule 5).

## Checks beyond the registered runs

Three checks on the dev output were read rather than registered, so they carry no figure for the README or the video.

- **On-hold and suggested wording (v2).** Every on-hold citation named the right substance (ashwagandha as *Withania somnifera*, reishi, curcumin). Claims that were also disease claims became possible breaches citing the on-hold entry, as the rule pack requires. All five suggestions were authorised magnesium wording, copied exactly, on magnesium claims; two sit on fear or deficiency claims (15.6.4, 15.8), where the suggested claim answers only part of the problem.
- **Precedent fit (v2).** 690 of 709 ruling citations shared a CAP rule family with their flag, but only 14 rulings were cited, and in a sample of ten pairs about half were about a similar claim. Retrieval is per ad, so the judge chooses from the same three rulings for every claim. v3 cut the citations by 29% at the same recall.
- **Over-reading on compliant ads.** Six invented ads, each an authorised claim copied exactly plus ordinary marketing lines (a general well-being line beside the specific claim, a pack size, a taste), were judged outside the split. v2 flagged two of them and v3 one, each time for a relaxation line ("Relax and recharge") cited as an unauthorised specific claim under 15.1.1, which is a call for a person. `judge_v4` flagged none of the 6. The probe was used while v4 was tuned, so this says little about v4, and v5 was not run on it.

## Caveats

- **The disease reading needs checking on real compliant ads.** In condition-targeted dev ads, v2–v5 call stress and calm claims disease treatment. The team negatives use only register wording and six invented ads are not a false-alarm rate; P33's error analysis should look at it.
- These are reconstructions, judged from the claims P26 extracted. The end-to-end figures on the test split (P33) are the ones to report.
- **Precedents are thin.** The index holds 33 rulings; a larger corpus would fit them better.

## For the founders

- **Rule precision is the next thing to improve.** A v6 that asks for the fewest rules each claim's own words breach should be written by a founder who has not read test-split ground truth or reconstructions, and checked against `claim_recall_exact_rules` and `rule_precision`, not `claim_recall` alone.
- **Prompt sign-off.** A founder reviews `prompts/judge_v5.txt` before it runs on the test split.
- **A read of the flags.** A founder reads a sample of v5's dev flags (`data/work/runs/check-20261101T210408/`).
- **False alarms.** Compliant ads that are not register-worded team ads (partner ads, P06) are the only way to get a false-alarm rate.
