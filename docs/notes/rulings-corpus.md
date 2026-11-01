# ASA rulings corpus (P13)

Built 31 Oct 2026 by `preflight.sources.rulings`. Raw pages are in `data/raw/rulings/` (git-ignored); the committed index `data/snapshots/rulings-2026-10-31.jsonl` holds ID, date, advertiser, media, outcome, CAP and BCAP rules and URL only, with no ruling text (`docs/source-terms.md`).

## How it was collected

- Window: formal rulings published 31 Oct 2023 to 31 Oct 2026.
- Candidates: the union of three searches on asa.org.uk's rulings page: the "Food, drink and supplements" topic filter (110 rulings), the phrase "food supplement" (80) and the phrase "health claims" (70). P02 used the two phrases. 146 distinct rulings.
- Fetched with 10 s between requests and an identifying User-Agent, as `docs/source-terms.md` requires. 145 pages in about 90 minutes, no errors or retries.
- **In scope** = cites a rule only a food health or nutrition claim can breach (15.1, 15.1.1, 15.2, 15.6.x, 15.7, 15.8, 15.9, 15.17), or the background or ad description mentions a supplement. One ruling is excluded by hand: G26-1332433 (Patisserie Valerie), a less-healthy-food placement case whose page links rule 15.9 where its text says 15.19.
- All 20 rulings in the P02 sample are in the corpus and in scope.

## Counts

| | Rulings |
|---|---|
| Candidates fetched and parsed | 146 |
| In scope | **77** (68 advertisers) |
| Out of scope | 69 (fast food and less-healthy-food placement, alcohol, price claims, vapes, a stem-cell clinic, a magnetic bracelet and similar) |

By outcome, in scope: **77 upheld, 0 upheld in part, 0 not upheld.** Every not-upheld or partly upheld ruling the searches returned (17) is about food placement, pricing or vapes, not health claims.

By year: 3 in late 2023, 29 in 2024, 25 in 2025, 21 in 2026 to date. 60 of the 77 mention a supplement; 66 cite a section 15 rule and 20 a section 12 rule.

By keyword topic (from the background and ad description; a ruling can fall in several, so this is a count aid, not a classification):

| Topic | Rulings |
|---|---|
| sleep, stress, mood | 37 |
| menopause and hormonal | 20 |
| gut and digestion | 18 |
| skin, hair, joints | 14 |
| weight loss | 12 |
| immunity | 11 |
| ADHD and autism | 11 |
| mushroom | 7 |
| children | 7 |
| magnesium | 5 |
| CBD | 5 |
| hangover | 1 |
| none of these | 11 |

**Informally resolved** cases are listed by name and date only, with no page, ad description or assessment, so they cannot be parsed into the corpus. The food topic listed 6 in the window (KFC, HelloFresh, Deliveroo and other food brands), none about health claims.

## What this means for P14

- **No not-upheld health-claim rulings exist in the window.** The negatives in split v1 have to be team-written ads using register wording (and partner ads if consent comes), as P02 predicted.
- **Mushroom (7) and magnesium (5) are too small to build two topics on.** Restricting v1 to them would give at most 12 positives before the two-per-advertiser cap. Sleep, stress and mood (37) and menopause (20) are the largest; ADHD (11) stays the hook. A topic-wide split of all 77 is the only way to reach 20 test positives plus a dev set.
- Ad descriptions are a separate field on every page parsed: all 146 have Ad description, Issue and Assessment headings, and a test checks that no assessment text leaks into the description.

## Widened for the precedent index (P27, 1 Nov 2026)

Split v1 uses 74 of the 77 in-scope rulings, which would leave the precedent index three. The same fetcher and scope test ran over formal rulings published 31 Oct 2019 to 30 Oct 2023: 63 candidates, all downloaded with 10 s between requests and no errors. Many are out of scope (alcohol, less-healthy-food placement). The new snapshot `data/snapshots/rulings-2026-11-01.jsonl` holds **112** in-scope rulings: the 77 above and 35 older ones, which date mostly from 2022 and 2023. The search returned few rulings from before 2021. Of the 38 in-scope rulings outside the split, 5 share an advertiser with a split ruling and are kept out of the index (`docs/notes/checker.md`). The `2026-10-31` snapshot is kept, because P26's registered runs name it.
