# Split v2 test items (P60)

Split v2 adds 20 team-written items to the test part: ten negatives, T26-T35, and ten near-miss items, N11-N20, each a test negative with one breaching line put in (P65). With the ten v1 negatives (T02-T14), the test part holds 20 negatives and 59 positives: 49 ASA rulings and 10 near-miss items.

## Who wrote them and who saw what

`docs/product-rules.md`, rule 5, keeps test items away from whoever writes or tunes the judge prompt. Since P65 and P70 the team has met it with an independent author: an AI assistant briefed from the `TeamAd` schema and the P60 deliverable list (written 2 Nov 2026), which never saw the judge prompt, its tuning, development results or the development review.

- **The author** read `docs/product-rules.md`, `src/preflight/eval/split.py`, `scripts/near_miss.py`, `tests/test_split.py`, the dev negatives T16-T25 (for style), the register snapshot `2026-05-19`, the 12.x and 15.x rules of CAP pack `2026-11-02` and `eval/splits/v2.yaml`. It opened no prompt, check code, run result, near-miss dev line or v1 team item.
- **The session that briefed it** saw item IDs, formats, register IDs, rule lists and test results, and none of the copy, product facts or breach lines. `scripts/inventory_test_items.py` checks the items' metadata and prints hashes and problem names only.
- **The checker** is a second AI assistant, separate from the author and under the same exclusions. It reads the copy and the renders, and reads each video's speech from a transcript of its audio (`docs/notes/decisions.md`, 2 Nov 2026, P60). A third assistant, also under those exclusions, checked the dev items T16-T25 and N01-N10.

`written_by` reads `assistant: ...` on all 20 items. `checked_by` takes the form `checker: checked <date>, media <first 12 characters of media_sha256>`, and the intake script lists the full hash.

## Checking an item

For each of T26-T35 and N11-N20, the checker opens `eval/items/team/<id>.yaml` and its render in `data/raw/team/<id>/`, transcribes every video's audio, and:

- for a negative, confirms that the ad makes no health claim beyond the register wording in `register_ids` and that it could run as it stands. That rules out an effect implied by the picture, an evening or recovery framing, a testimonial, or an unprovable "gentle on the stomach" (#59, "Watch out");
- checks that the fictional product facts in the file's comments meet each register entry's conditions, and that the ad gives any information the conditions require;
- for a near-miss item, confirms that the inserted line breaches on its own and that its rules in `eval/ground_truth/v2/<id>.json` are right;
- sets `checked_by`, or raises the line that fails.

The author flagged these doubts, and the checker settled them on 2 Nov:

| Item | Doubt | Settled |
|---|---|---|
| T30 | A warning the register's conditions require names a physical difficulty outside the register wording; the author treated it as required information. | Compliant: the conditions require the warning, and a required warning is not a health claim. |
| T28, T34 | The amount per tablet is well above the "source of" level, in one case several times the reference intake. | Plausible: both meet the "source of" level and sit below the UK expert safe upper levels. |
| T29, T31 | Amounts the conditions don't require the ad to state appear only in the file's comments. | Fine: the conditions require only a "source of" level, which the attested facts meet. |
| N15 | The line adds a timeframe to a claim about a blood level; the checker decides whether it also reads as treating a condition (15.6.2). | No 15.6.2: the line names no condition. Rules unchanged. |
| N19 | The line suggests fat loss, which may also breach the weight-control rules; none were added. | Not added: 13.9, 13.10.1 and 15.6.6 need figures, a timeframe or spot reduction, and the line gives none. |
| N12, N16, N18 | These disease claims may also breach 12.1; it was left out. | Added 12.1, 15.1.1 and 15.7, to the rules in `eval/near_miss/test.yaml` and the ground truth. |

The checker also found that drawtext dropped any on-screen line with a % sign, which blanked a line of T28 and N13. The overlay now draws with `expansion=none`; both were rendered again, rechecked and signed. The same fault hid one on-screen line in seven dev reconstructions (A24-1241017, A24-1241337, A24-1241024, A24-1241022, A24-1228813, G23-1215538, A23-1216841) in every dev run registered before the fix.

A third checker went through the dev items, T16-T25 and N01-N10, and signed all twenty. On the way it labelled N03 both a disease claim and an overstated claim (15.1, 15.1.1, 15.6, 15.6.2, 15.7), and found three faults in base ads, each since fixed. T19 and T21 showed two kinds of tablet or capsule against a one-a-day dose, because the image model drew a combined product as two; the still prompt now asks for one product with identical units, and T19, T21, N04 and N06 were rendered again. T24 offered a subscription without its terms (CAP 3.3), so that line left T24 and N09, which were rendered again. Dev runs registered before 2 Nov evening screened the old renders of these six items. Its transcripts of the dev videos repeat some words; splitting the audio moved or removed the repeats, so they are transcription faults and the speech is as written.

## What the pass mark can show

The false-alarm pass mark is an acceptance rule on copy the team wrote, and the false-alarm rate it measures applies to that copy, not to customer ads. Counts register exact (Clopper-Pearson) 95% intervals over ads (P64). With no ad flagged, the upper bound falls slowly with the number of negatives (rounded up, as the registry prints bounds):

| Negatives | Two-sided upper bound | One-sided upper bound |
|---|---|---|
| 10 | 30.9% | 25.9% |
| 20 | 16.9% | 14.0% |

A zero-event one-sided bound falls below 10% only at 29 negatives, and below 5% at 59.

A threshold also trades the two kinds of error. If each ad were flagged independently at a true rate p, the chance of passing would be:

| Rule | p = 5% | p = 10% | p = 20% |
|---|---|---|---|
| 0 of 10 flagged | 59.9% | 34.9% | 10.7% |
| at most 1 of 10 | 91.4% | 73.6% | 37.6% |
| 0 of 20 flagged | 35.8% | 12.2% | 1.2% |
| at most 1 of 20 | 73.6% | 39.2% | 6.9% |

A judge that flags nothing passes any false-alarm rule, so the pass mark needs a recall bar beside it. The agreed pass mark is at most 1 of the 20 test negatives flagged, beside `ad_recall` of at least 48 of 59 and `near_miss_caught` of at least 9 of 10 (`docs/notes/decisions.md`, 2 Nov 2026, P60).

## What the write-up has to own

- **Origin cue.** Team ads carry the overlay "Team-written test ad" and reconstructions "AI reconstruction from ASA ruling text" (`team_media.LABEL`, `reconstruct.LABEL`). Both reach the judge through on-screen text, so on every item except the near-miss items the overlay tells the judge which label to expect. The near-miss items carry the team overlay and are positives: judge_v7 caught all ten dev items (`screen-20261102T182225`), which suggests the overlay does not stop the judge from flagging a team ad, but does not test whether it lowers flags on the negatives.
- **Conditions of use.** The judge sees each register entry's ID, status, substance and wording, without its conditions. A negative's label assumes the fictional product meets those conditions, which the screen cannot check from the ad.
- **Coverage.** Twenty negatives on plain product stills, the videos with synthetic narration, cover no motion, imagery that implies an effect, noisy audio or customer layouts.
