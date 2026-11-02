# Claim extraction (P26)

Measured 1 Nov 2026 on the 25 dev positives of split v1. Every number below comes from a run registered in `results/runs.csv`; per-item rows are in `results/runs/<run_id>.csv`.

## What the stage does

`preflight.claims.extract_claims` makes one Muse Spark call per ad (Standard mode, strict JSON schema). The call carries the video or still and a list of the transcript segments, on-screen texts and SAM tracks the earlier stages found. The model returns each claim's text, whether it is explicit or implied, the substance it names, and the IDs of its evidence. The schema restricts evidence to an enum of the IDs in that list, so a claim cannot cite evidence the screening does not hold; a claim with no text or no evidence raises. A claim on a track is shown at the track's cropped frame. Repeated claims are merged with all their evidence.

The issue asked for each claim's effect as well. `Claim` has no field for it and adding one would bump the schema version, so the claim text carries the effect.

Settings: prompt version, reasoning effort, and an optional second pass that shows the model its first list and asks for what it missed (`prompts/claims_missed_v1.txt`).

## How recall is scored

`uv run --extra align python -m preflight.eval.claim_recall [--prompt claims_v3] [--effort high] [--second-pass]` screens each dev reconstruction (dev only; rule 5) and matches the extracted claims to the ground truth.

A ground-truth claim counts as found when at least 80% of its words appear, in order, in one extracted claim, and that claim is at most twice as long as the ground-truth claim, or five words longer when that allows more. The length limit matters. Without it, a prompt that quotes whole sentences scores well because one long quote covers several claims: prompt v2 found 227 of 250 claims that way but only 143 under the limit. Each run reports both figures (`claim_recall` and `claim_recall_loose`).

Two ceilings sit below 250. The reconstructions genericise brand and product names, which drops 12 claims (`claim_recall_carried` counts against the 238 that remain). Another 6 never reach the transcript or the on-screen text (`lost_upstream`). No prompt can find these 18, so 232 is the most any configuration can reach on these ads.

## Results

| Run | Prompt | Effort | Passes | Ads with a claim found | Claims found | Claims per ad | Cost per ad | Seconds per ad |
|---|---|---|---|---|---|---|---|---|
| claims-20261101T014006 | v1 | medium | 1 | 25 of 25 | 163 of 250 | 20 | $0.044 | not timed |
| claims-20261101T014139 | v2 | medium | 1 | 25 of 25 | 143 of 250 | 13 | $0.035 | not timed |
| claims-20261101T014337 | v3 | medium | 1 | 25 of 25 | 197 of 250 | 27 | $0.046 | 35 |
| claims-20261101T020134 | v3 | medium | 2 | 25 of 25 | 205 of 250 | 33 | $0.091 | 72 |
| **claims-20261101T023641** | **v3** | **high** | **1** | **25 of 25** | **209 of 250** | **29** | **$0.062** | **53** |

Ad counts for the first three runs are read from their per-item rows; the `ad_recall` metric was added after them. Costs are for the claim-extraction calls only, at published prices. Runs v1 and v2 reused cached answers recorded before call times were kept.

The default is now v3 at high effort: 209 of the 250 ground-truth claims (84%), or 209 of the 238 the reconstructions carry. A second pass at medium effort found fewer claims at higher cost. Each configuration ran once, so differences of a few claims are within run-to-run variation; the step from v1 to v3 is not.

The first runs of v1 and v2, `claims-20261101T005513` and `claims-20261101T012247`, were scored before the length limit existed, so the registry lists their figures as `claim_recall_loose`. Their tight scores are the v1 and v2 rows above, rescored from the same cached answers.

The second-pass and high-effort runs ran at the same time, so their seconds per ad include any slowdown from sharing the API.

## Prompt versions

Prompts are written from the CAP rule pack and the labelling rule in `docs/plan.md` only. A test fails if any ruling ID, or any ground-truth claim of three or more words from either part of split v1, appears in a `prompts/claims_*` file (`docs/notes/decisions.md`, 1 Nov 2026).

- **v1** lists the kinds of claim the CAP Code covers and asks for the smallest passage that makes each claim. It splits lists into fragments and misses whole sentences, testimonials, safety claims and symptoms the ad sets up for the product.
- **v2** adds those kinds and asks for lists to be kept whole. It finds the sentences but loses the short claims inside them.
- **v3** keeps v2's kinds and asks for both: the whole phrase and each claim inside it.

Tuning stopped at v3. Of its 41 misses at high effort (`claims-20261101T023641`, listed in that run's `details.json`), 13 are product and range names or contain one. Eight are short energy and focus claims in two ads that repeat such claims many times, where the model gives some forms and not others. The rest are single cases that a general instruction would not reach without fitting individual dev ads.

## Parser integration review (1 November)

Duplicate claims are merged by normalized wording, claim kind and substance. Substance
comparison ignores capitalization and repeated whitespace; it does not infer chemical
aliases. Identical wording about different substances keeps separate evidence and
claim IDs. A repeat with no substance joins the named claim only when exactly one
substance appears across those repeats; otherwise it remains a separate unnamed
claim. This avoids silently assigning evidence to whichever substance arrived first.

This parser correction was verified on synthetic regressions after the historical
registered runs above. Their measured figures have not been recomputed and must not
be presented as measurements of the corrected integration.

## Caveats

- These are reconstructions rebuilt on 1 Nov with the same builder (`docs/notes/reconstructions.md`), not the set the founders' spot-check covers. Real ads have faster cuts, smaller print and real voices.
- Claim recall measures listing. Whether each claim is judged a breach is the checker's job (P27), and the end-to-end figure on the test split (P33) is the one to report.
- v3 lists about 29 claims per ad, which the checker has to sort through.
- The Spark client retries only rate-limit errors. One run stopped on a transient failure and was rerun from the cache; the screening path (P28) needs retries for server errors too.

## For the founders

- **Names that carry claims.** Product names such as "Happy Mind" are breaches in themselves, but reconstructions drop them. Either the shot-list prompt keeps claim-bearing names or P31 scores those claims as not reconstructable (raised in `docs/notes/reconstructions.md`).
- **The bar for the test run.** Agree before P33 what ad-level recall, claim-level recall and false-alarm rate count as good enough to report.
- **Prompt sign-off.** Neesay or ADI-0519 reviews `prompts/claims_v3.txt` before it runs on the test split.
