# Verified facts

Facts the video, README or page may quote about the ASA, the register and the CAP Code, each read in its primary source (task P07). Quotes are verbatim. "PDF page" counts pages in the PDF file, since the reports print no page numbers. All sources were read on 31 Oct 2026; local copies are in `data/raw/p07/` (git-ignored).

## ASA Pulse Report: health claims in online ads

Source: "Pulse Report: Understanding health claims in online ads", listed on asa.org.uk as published 01 Oct 2026 (`https://www.asa.org.uk/resource/pulse-report-health-claims-in-online-ads.html`); the PDF cover says "September 2026".

| Fact | Exact wording | PDF page |
|---|---|---|
| Ads captured | "We found 309,000 relevant ads and used expert review to identify seven health topics of greatest regulatory concern for deeper assessment." | 4 |
| Ads in the seven topics | "Across these seven topics, we identified 30,180 ads in total." | 4 |
| Ads rated by hand | "In total, we assessed and rated 582 individual ads." | 4 |
| The 86% figure | "In every group reviewed, more than 86% of ads were rated as medium or high compliance risk, indicating widespread likely breaches of the rules." | 5 |
| What "medium" means | "Ad is likely to breach the Code, but would require further investigation to confirm, and presents no serious health or safety risk in isolation." | 30 |
| Not formal findings | "This analysis was not intended to make formal compliance determinations." | 33 |
| Capture window | "shown between 26 May and 22 June 2026 inclusive" | 32 |
| Mushroom supplements | 2,440 ads; "53% were high risk and 84% referenced symptoms or conditions." | 4, 12 |
| Magnesium supplements | 4,270 ads; 91% medium risk | 4, 18 |

How to quote the 86% figure: always with its denominator, for example "more than 86% of the ads the ASA rated by hand in each of seven priority health topics (582 ads in all) were medium or high compliance risk". Never say "86% of 309,000 ads", and never call medium-risk ads breaches: the ASA says each would need further investigation to confirm.

Two cautions:

- The report gives two figures for magnesium's high-risk share: 4% in the table on PDF page 4 (whose row reads 5% low, 91% medium, 4% high), and 5% in the chart on page 11 and the text and panel on page 18. Checked on the rendered pages. Don't quote either.
- Mushroom and magnesium supplements are two of the report's seven priority topics (PDF page 10). This is primary support for the provisional topic choice in `docs/notes/decisions.md`.

## CAP enforcement report: ADHD and ASD claims in food supplement ads

Source: listed on asa.org.uk as published 15 Oct 2026 (`https://www.asa.org.uk/resource/enforcement-report-adhd-and-asd-claims-in-food-supplement-ads.html`); the PDF cover says "August 2026". Cite it as published 15 Oct 2026.

| Fact | Exact wording | PDF page |
|---|---|---|
| Ads captured | "we captured 72.4k unique paid ads for food supplements that appeared relevant to ADHD and ASD on Meta and Google between February and July 2026" | 2 |
| Ads that broke the rules | "it was found that 1,383 ads by 17 advertisers broke the rules" | 2 |
| Compliance, February | "When monitoring began in February 2026, the proportion of compliant ads was 4.7%." | 3 |
| Compliance, June | "Following the second sweep (June 2026), compliance rose to 31.2%." | 3 |
| Compliance, July | "Following the third sweep (July 2026), compliance dropped to 8.6%." | 3 |
| Compliance, April (Figure 1 only) | 1.2%, read from the chart; the text skips April | 3 |
| July covers part of the month | Figure 1 footnote: "July includes monitoring through 13 July 2026" | 3 |
| Volume fell | "By July 2026, the number of ads fell to less than a quarter of pre-contact levels." | 4 |
| Example claims | "fixes ADHD in 30 days", "no more meltdowns" | 2 |

## CAP enforcement report: prostate tests and supplements

Source: listed on asa.org.uk as published 15 Oct 2026; the PDF cover says "September 2026".

| Fact | Exact wording | PDF page |
|---|---|---|
| Prostate supplements, compliance | "When monitoring began in February 2026, the proportion of compliant ads was 0.5%. By July 2026, the compliance rate was 0.6%." | 2 |
| Prostate supplements, volume | "By July 2026, the number of ads from these advertisers had decreased to 180." (835 in April) | 2 |
| PSA home tests, compliance | "compliance rates for PSA home testing kit ads increased from 20.0% to 64.5% during the monitoring period" | 4 |

## ASA Active Ad Monitoring

Source: `https://www.asa.org.uk/about-asa-and-cap/the-work-we-do/active-ad-monitoring-system.html`.

- "In 2025, the system processed more than 60 million ads and supported over 30 regulatory projects."
- "ASA experts then review and assess the ads identified by the system and decide whether any action is needed."

The "over three million online ads a month" figure (a July 2024 spokesperson quote) is not on this page. Use the 2025 figure instead.

## GB nutrition and health claims register

Source: `https://www.gov.uk/government/publications/great-britain-nutrition-and-health-claims-nhc-register`, Department of Health and Social Care.

- **Licence:** the GOV.UK footer states "All content is available under the Open Government Licence v3.0, except where otherwise stated". The publication page states nothing otherwise. The licence (`https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/`) lets us "copy, publish, distribute and transmit the Information", "adapt the Information" and "exploit the Information commercially and non-commercially". The provider gives no attribution statement, so we must use: "Contains public sector information licensed under the Open Government Licence v3.0." The licence also bars any use that "suggests any official status" or endorsement.
- **Dates:** published 31 December 2020, last updated 19 May 2026. That update "added one non-authorised claim (006UKNHCC for green kiwifruit powder)" and added Excel versions of the register and annex.
- **Files:** the register as ODS (374 KB) and XLSX (320 KB), and an annex of "health claims authorised on the basis of proprietary data" as ODS and XLSX, dated 27 February 2025.
- **Scope:** "Only authorised claims in the Great Britain NHC register may be used in Great Britain." The page applies to England, Scotland and Wales; CAP section 15 says the EU Register still applies in Northern Ireland.

The XLSX of 19 May 2026 holds two sheets, `Health_claims` and `Nutrition_claims`. `Health_claims` has these columns: Claim type; Nutrient substance, food or food category; Claim; Conditions of use of the claim / Restrictions of use / Reasons for non-authorisation; Health relationship; Scientific Opinion Reference; Regulation; Status; Entry Id. The counts below come from reading that file:

| Count | Value |
|---|---|
| Rows with claim text | 2,349 (206 more rows continue a reference from the row above) |
| Status "Authorised for use in Great Britain" | 261, plus 6 marked `*` (proprietary data, also in the annex) |
| Status "Non-authorised" | 2,082 |
| Authorised rows whose Entry Id is "not applicable" | 38 |
| Authorised rows with more than one Entry Id (e.g. "240, 247, 248") | 129 |
| Authorised rows that share an Entry Id value with another row | 63 |
| Authorised rows with a substance containing "magnesium" | 10 |
| Authorised rows with a substance containing "mushroom" | 0 |
| Rows naming a mushroom species (shiitake, oyster, king oyster, maitake, cordyceps, reishi) | 9, all "Non-authorised" |

What this changes:

- **Entry Id is not a register ID.** It is missing, repeated or multi-valued for many authorised claims, so it cannot serve as the register ID for rule 2. P11 derives its own `register_id` from six columns (`docs/notes/register.md`).
- **No authorised wording exists for mushroom ingredients**, so under rule 2 a mushroom-supplement ad gets no suggested wording, and the agent fix loop needs a topic like magnesium (10 authorised claims) to show a rewrite. Authorised beta-glucan claims name oats or barley, plus one generic "Beta-glucans" entry, whose conditions of use have not been checked against mushroom-derived beta-glucans.
- **A missing or non-authorised mushroom claim is not by itself a breach**, because of the "on hold" list below.

## "On hold" health claims

The register is not the only list that decides whether a claim may be used in Great Britain.

- DHSC guidance (`https://www.gov.uk/government/publications/nutrition-and-health-claims-guidance-to-compliance-with-regulation-ec-1924-2006-on-nutrition-and-health-claims-made-on-foods/nutrition-and-health-claims-guidance-to-compliance-with-regulation-ec-19242006`, updated 10 November 2021), section 1.12: "'On hold' claims may continue to be used in accordance with the 2014 Bulletin until a decision is made following the call for evidence."
- The same guidance, section 1.10, names two exceptions to "only authorised health claims": "general, non-specific claims (subject to the conditions of Article 10.3 of retained Regulation (EC) No. 1924/2006)" and "trademarks or brand names that are also health claims".
- The list: "Article 13(1) 'on hold' health claims" (`https://www.gov.uk/government/publications/on-hold-health-claims-on-foods`, DHSC, last updated 12 January 2021, ODS only), which "sets out the 'on hold' health claims that may continue to be used in Great Britain". It holds 2,078 botanical claims and 17 other claims (caffeine, for example), each with a numeric Claim ID, the health relationship and the wording "proposed by applicants in 2008".
- The list includes mushroom claims: Ganoderma lucidum (reishi) for immune defences, circulation and blood cholesterol, and Agaricus blazei for natural defences. It also has two magnesium lactate combinations for calm and stress.
- Its own notes limit it: claims also listed as non-authorised "can no longer be used so you should check in the Register, as well as this spreadsheet"; "Many of the proposed claim wordings may not be acceptable under the general provision of Regulation (EC) 1924/2006 or general labelling rules"; and some "may be construed as medicinal claims and must not be made on foods".
- CAP's AdviceOnline entry "Food: Health claims" (`https://www.asa.org.uk/advice-online/food-health-claims.html`) says on-hold claims are "still under consideration by the UK government and devolved administrations" and advises marketers "to seek advice from the DHSC". It cites rulings against ads that claimed on-hold status without evidence (A Nelson & Co Ltd, 11 March 2015) or that held an on-hold claim but lacked "sufficiently robust evidence" (Pharma Nord (UK) Ltd, 10 December 2014; New Nordic Ltd, 14 October 2015).

What this changes:

- "No authorised register entry" does not mean "breach" for botanical ingredients. The on-hold list is snapshotted on its own (`data/snapshots/on-hold-2021-01-12.jsonl`, loader `preflight.sources.on_hold`), and the `15.1.1` entry in the CAP rule pack now says an on-hold match is not a breach of that rule. P27's checker should report a claim that matches an on-hold entry as on hold, with that entry as its source, not as an unauthorised claim. Otherwise it will raise false alarms on usable claims.
- Whether rule 2 lets on-hold wording appear as suggested wording is a founders' call. The list's own notes say much of its wording may not be acceptable, so the safe reading is: suggest only authorised register wording, and cite on-hold entries as context.

## CAP Code section 15

Source: `https://www.asa.org.uk/type/non_broadcast/code_section/15.html` (the section page, which `robots.txt` allows; the `code_rule/` pages are disallowed, see `docs/source-terms.md`). The page carries no edition or revision date, so cite it as "CAP Code section 15, read 31 Oct 2026".

Rules we expect to cite:

| Rule | Subject | Short quote |
|---|---|---|
| 15.1 | Documentary evidence that claims meet the register's conditions of use | "Claims must be presented clearly and without exaggeration." |
| 15.1.1 | Only register claims may be used | "Only health claims listed as authorised in the applicable register, or claims that would have the same meaning to the consumer, may be used in marketing communications." |
| 15.2 | General well-being claims | "acceptable only if accompanied by a specific authorised health claim" |
| 15.6.2 | Disease claims | "Claims that state or imply a food prevents, treats or cures human disease." |
| 15.6.3 | Health professional recommendations | – |
| 15.6.4 | Exploiting fear about bodily functions | – |
| 15.6.6 | Rate or amount of weight loss | – |
| 15.7 | Food supplement claims must be authorised as at 15.1.1 | – |
| 15.8 | Implying a balanced diet is not enough | – |

The 27 rulings saved in `data/raw/asa-rulings/` also cite rules outside section 15. Counting rulings whose text mentions each rule number: 15.6.2 in 15, 15.1 and 15.1.1 in 14, 12.1 in 11, 12.11 in 8, 3.1 in 8 and 3.7 in 6. These rules come from section 12 (`https://www.asa.org.uk/type/non_broadcast/code_section/12.html`, "Medicines, medical devices, health-related products and beauty products") and section 3 (`https://www.asa.org.uk/type/non_broadcast/code_section/03.html`, "Misleading advertising"), both read on 31 Oct 2026:

| Rule | Short quote |
|---|---|
| 12.1 | "Objective claims must be backed by evidence, if relevant consisting of trials conducted on people." and "A medicinal claim is a claim that a product or its constituent(s) can be used with a view to making a medical diagnosis or can treat or prevent disease in human beings." |
| 12.2 | "Marketers must not discourage essential treatment for conditions for which medical supervision should be sought." |
| 12.11 | "Medicines must have a licence from the MHRA, VMD or under the auspices of the EMA before they are marketed." |
| 3.1 | "Marketing communications must not materially mislead or be likely to do so." |
| 3.7 | "marketers must hold documentary evidence to prove claims that consumers are likely to regard as objective and that are capable of objective substantiation" |

A supplement ad that claims to treat a condition is typically cited under 15.6.2 and also 12.1 or 12.11 (an unlicensed medicinal claim), so a section-15-only rule pack would miss rule numbers the ASA cites in about two in five of these rulings. The P12 rule pack covers all of these (`data/snapshots/cap-2026-10-31.yaml`).

## Meta Model API: training and retention

Follow-up to `docs/notes/meta-model-api-findings.md` (P03) for rules 6 and 10. Source: `https://dev.meta.ai/docs/pricing-rate-limits` and `https://dev.meta.ai/docs/file-handling`, read 31 Oct 2026.

- **Standard mode does not train on our content.** "In Standard mode, you pay standard prices and your content is not used to train Meta models." Contributor mode is the opposite: "permission to use your content — the prompts, code, files, and context you send, plus the model responses you get back — to train future Meta models". Rule 10 stands as written.
- **Voice Transcribe has no Contributor mode**: "Contributor mode isn't available for Muse Voice Transcribe." The same page names a zero data retention option: "Zero data retention (ZDR) is priced at parity with Standard mode." How to turn ZDR on is not described on the pages read.
- **Uploaded files are kept until deleted.** "Uploaded files don't expire, so stored data only grows until you remove it." An upload can set `expires_after` with `anchor: created_at` and `seconds` "from 3600 (1 hour) to 2592000 (30 days)". For rule 6, the model client (P22) should set `expires_after` on every upload and delete the file once the screening finishes. `scripts/smoke_models.py` did neither, so the P03 test clip is still stored on the team's account; it is our own synthetic ad, so this is cleanup, not a breach.
- **Responses are stored.** The API reference has "Retrieve a stored model response by ID" and a delete endpoint. How long a response is kept is not stated on the pages read.
- **`store=False` turns storage off (P67).** Checked live on 2 Nov 2026 against `muse-spark-1.3`: with `store=False` the response echoes `store: false` and retrieving it by ID returns 404; the same request with `store=True` echoes `store: true` and can be retrieved. Both `responses.create` calls in `preflight.models.clients` set `store=False`.
- **No terms of service page is linked from the docs.** The binding terms are the ones accepted at sign-up on dev.meta.ai; a founder should save a copy from the account.

Follow-up, 4 November 2026: the [public Meta Model API terms](https://dev.meta.ai/legal/terms-of-service)
are now accessible (dated 9 October 2026). Section 5.1 excludes using content
submitted to Standard Services to train Meta Models. The product page links this
source. This confirms a contractual training exclusion, not zero provider retention
or private account isolation in PreFlight.

## Hackathon Official Rules

Follow-up to `docs/notes/hackathon-rules.md` (P01). On 31 Oct 2026 both public event pages (`cerebralvalley.ai/e/meta-ai-developer-hackathon`, `dev.meta.ai/events/global-hackathon`) still say "Official Rules will be published before the Hackathon begins on October 26, 2026 and must be accepted by the selected participants", with no link. The participant Notion page renders only in a browser. The rules are therefore readable only by a logged-in founder.

## Still needs a founder

Each item below can't be done from public pages or needs someone outside the team.

| Item | From | Who |
|---|---|---|
| Read the formal Official Rules logged in and fill in the IP, licence and third-party content rows of `docs/notes/hackathon-rules.md` | P01 | any founder |
| Ask the organisers the two gate 1 questions in `docs/notes/hackathon-rules.md` before P15 starts | P01 | any founder (contacts the organisers) |
| Confirm all three founders are approved participants on the team | P01 | each founder |
| Save a copy of the Model API terms accepted at sign-up; check how to enable zero data retention | P03 | account owner |
| Check the billing page against the P03 cost estimates | P03 | account owner |
| Delete the P03 test file from the team's Files storage | P03 | anyone with the key |
| Confirm the P05 decisions, which one founder took on 31 Oct (`docs/notes/decisions.md`) | P05 | the other two founders |
| Decide whether on-hold wording may ever be suggested under rule 2 | P07 | all founders |
