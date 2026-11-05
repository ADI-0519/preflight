# Evaluation

PreFlight is measured on ads whose breaches are already known: ads the ASA has ruled on, rebuilt from the rulings' own descriptions. This page sets out how the test items are made, how a screening is scored against them, what keeps the test rulings out of the system, and how runs are recorded. The results themselves are in [results/final.md](../results/final.md), generated from the run registry.

## Items

**Rulings.** The corpus holds formal ASA rulings published from 31 October 2023 to 31 October 2026 that cite a rule only a food health or nutrition claim can breach (15.1, 15.1.1, 15.2, 15.6.x, 15.7, 15.8, 15.9, 15.17), or whose background or ad description mentions a supplement. That gave 77 rulings, every one upheld. Capped at two per advertiser, 74 remain, split by date: the 25 oldest (November 2023 to September 2024) form the development part and the 49 newest (September 2024 to October 2026) the test part. The precedent index the check retrieves from draws on a wider corpus, back to October 2019.

**Ground truth.** Each ruling item lists its breaching claims. A breaching claim is the smallest passage of the ruling's ad description that an upheld point of the assessment found in breach, quoted exactly, with that point's CAP rules. A claim upheld under several points is listed once with all their rules. A quote that covers several claims is split, a fragment inside another claim is dropped unless it is a breach on its own, and quoted text that is not a claim (a name, a hashtag) is removed. A script drafts each list from the ruling, and every list was then corrected by hand against the ruling page.

**Reconstructions.** Ruling pages carry a text description of the ad and no image or video, so each ad is rebuilt from the "Ad description" section and nothing else. The builder's input type holds that section only, and a test checks that no assessment text reaches a model request. Muse Spark writes a shot list that keeps the quoted wording exactly and replaces brand and person names with generic ones. Muse Image draws a picture for each scene with no text in it. All wording is then drawn on with ffmpeg so it stays exact, and a local text-to-speech voice reads any voiceover. Every frame is labelled "AI reconstruction from ASA ruling text". An automatic check compares each rebuild's wording with its ad description. Claims that lived only in a brand or product name ("Happy Mind", a comparison with a named drug) cannot survive the name being replaced, so recall is reported over the claims the reconstruction carries as well as over all of them.

**Clean ads.** No in-scope ruling in the window was not upheld, so the negatives are ads written for the purpose. Each makes only claims that its register entries authorise, and its product facts meet those entries' conditions of use. They are rendered as images or videos by the same assembly as the reconstructions, labelled "Team-written test ad".

**Near-miss ads.** A near-miss ad is a clean ad with one breaching line added: on screen before the food supplement statement in an image, or at the end of the voiceover in a video. Most of these lines overstate the ad's own authorised claim ("Vitamin C supercharges your immune system", where the register allows "contributes to the normal function of the immune system"). The rest are disease claims. They test the case a reviewer meets most often: an ad that is mostly fine with one bad line.

The clean ads and near-miss lines added to the test part in split v2 were written and checked by AI assistants that never saw the judge prompt, its tuning or any development result, so whoever tuned the prompts could not shape those items.

## Split

A split lists item IDs in a `dev` part and a `test` part (`eval/splits/`). Prompts and thresholds are tuned on `dev` only. `test` runs once per final configuration. A split is frozen once every item is checked, and any change to either list makes a new version, never an edit.

| Split v2 | Ruling ads | Near-miss ads | Clean ads | Total |
|---|---|---|---|---|
| dev | 25 | 10 | 15 | 50 |
| test | 49 | 10 | 20 | 79 |

The test part's 49 ruling ads carry 559 ground-truth claims, of which the reconstructions kept 530.

## Leakage

Held-back rulings never appear in prompts, few-shot examples, retrieval indexes or tuning. During evaluation each item gets its own precedent pool for the check's ruling retrieval. Test rulings, and every ruling on a test advertiser, are left out. An item can see only dev rulings published before its own, excluding its own ruling and any on its advertiser. Without the date rule a run cited rulings from the same ASA sweep as the item, so that run is void and listed in `results/void.csv`. Outside evaluation, the CLI, the API and the agent tools leave every split ruling out of the index.

## Scoring

A ground-truth claim is **caught** when a flag's claim contains its words in order (at least 80% of them), is no longer than twice the claim or the claim plus five words, and cites one of the claim's CAP rules or a rule above or below it (15.6 matches 15.6.2). A flag that matches the claim but cites only unrelated rules does not count as a catch; it is reported separately.

| Metric | What it counts |
|---|---|
| `ad_recall` | Positive ads with at least one caught claim |
| `claim_recall_carried` | Caught claims over the claims the reconstruction carries; the headline claim figure |
| `claim_recall` | Caught claims over every ground-truth claim |
| `claim_recall_carried_by_chance` | Expected catches if the flags that match each claim cited their rules at random; a floor for the rule-matching part |
| `claim_recall_carried_weighted` | Each catch weighted by the best share of a matching flag's rules that belong to the claim |
| `rule_precision` | Cited rules that match a rule the ASA cited for that claim |
| `near_miss_caught` | Near-miss ads whose inserted line is caught |
| `clean_lines_flagged` | Lines of near-miss ads, other than the inserted one, that a flag lands on |
| `negative_ads_flagged` | Clean ads with any flag; on a clean ad every flag is a false alarm |
| `unmatched_lines_per_positive_ad` | Flagged lines on a ruling ad that match no ground-truth claim; counted, not scored, since a ruling does not list everything wrong with an ad |

Results are reported as counts with their denominators, never as a single accuracy figure. Intervals are 95%: exact Clopper-Pearson intervals for counts of ads, and percentile bootstraps over ads (2,000 draws, fixed seed) for counts of claims, lines and rules, so the claims of one ad move together.

## Baseline

The keyword baseline screens the same items with no model calls and is scored by the same code. It flags a sentence that names a register substance and a benefit term ("supports", "immune") without the wording of an authorised entry for that substance, under rules 15.1 and 15.1.1. It also flags a sentence that names a disease, condition, symptom or cure word, under 15.6 and 15.6.2. Words inside an authorised wording are not checked, since some entries name a condition ("normal thyroid function").

The baseline reads each ad's text as written. PreFlight has to read the same text off the rendered media through transcription and on-screen reading, so its errors there count against it and not against the baseline. Both word lists were written after the development items had been read. They hold general vocabulary and no ruling's wording, but they may suit those items better than unseen ads.

```
uv run python -m preflight.eval.baseline --split v2 --part dev
```

## Records

```
uv run python -m preflight.eval.run --split v2 --part dev
```

screens every item of a part end to end through the shared pipeline, scores it, and registers the run in `results/runs.csv`. The registry has one row per metric, with hits, total and interval, and records the split version, part, model and prompt versions, reasoning effort, snapshot versions, git commit (marked `-dirty` for uncommitted code) and cost. Per-item rows go to `results/runs/<run>.csv`. A run with a failed stage, or with a screening whose check did not finish, writes its per-item rows but is not registered. A test run is refused from a tree with any uncommitted or untracked file. `--rescore RUN_ID` scores a saved dev run again with no model calls.

`uv run python -m preflight.eval.final` writes `results/final.md` from the registered test run and its baseline. Every figure in the README and on the web page's scoreboard comes from that file or from the registry, never typed by hand.

## Limits

### Registered test execution and replay

The first 79-item test execution did not register because an item failed source
validation. A source-reference fix retained the judge's in-shortlist citations
when substance filtering would otherwise leave a flag unsupported; suggested
wording remained restricted to the claim's substance. The registered run
`screen-20261104T052428` replayed the first execution's saved model answers rather
than judging the items again. Its $24.15 records the original model usage.

The registered configuration used turn timing (`--no-align`). The web API now
enables local word alignment by default where available, so the historical result
does not measure every current input and configuration combination.

Replay requires the original recordings, inputs and source assets, including files
excluded from the public repository. Fresh model calls may differ. Historical
run commit IDs predate the repository transfer and refer to its original history.
Contributor and reviewer labels were normalised during that transfer; matching
display labels cannot substantiate independent authorship or review. Original
provenance and internal working notes are retained separately.

### Generalisation

- Reconstructions are rebuilt from text, so they test what an ad says and shows as the ruling describes it, and they cannot test how a real production looks. One reconstruction lost the before-and-after picture its ruling partly rests on, because the image model refused it.
- Every clean ad is written for the purpose. None is a real ad the ASA cleared.
- The test rulings are later than the development ones and lean more on CAP Code section 12, medicinal claims: about 26% of the rules the ASA cited in the test part against about 1% in the development part.
- A ruling does not list every problem in an ad, so flags that match no ground-truth claim are counted and left unscored.
