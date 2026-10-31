# Data

`data/raw/` is git-ignored: downloads stay on the machine that fetched them. `data/snapshots/` holds processed, dated snapshots that are committed when the source's licence allows it.

## GB nutrition and health claims register

| | |
|---|---|
| Page | https://www.gov.uk/government/publications/great-britain-nutrition-and-health-claims-nhc-register |
| File | https://assets.publishing.service.gov.uk/media/6a0c4faf229555d0fe826835/great-britain-nutrition-and-health-claims-spreadsheet-19-may-2026.xlsx |
| Release | 19 May 2026 (the page's "Last updated" date) |
| Downloaded | 31 Oct 2026, to `data/raw/register/great-britain-nutrition-and-health-claims-spreadsheet-19-may-2026.xlsx` |
| SHA-256 | `761dcf52c797d257c1d6b4dc8a516eea1438828e4d5496851176e2854ca1775c` |
| Size | 327,922 bytes |
| Publisher | Department of Health and Social Care |
| Licence | Open Government Licence v3.0. The page footer reads "All content is available under the Open Government Licence v3.0, except where otherwise stated"; the page states no exception for this file. © Crown copyright. |
| Snapshot | `data/snapshots/register-2026-05-19.jsonl`, committed (OGL allows copying, publishing and adapting with attribution) |

Rebuild the snapshot from the download:

```
uv run python -m preflight.sources.register data/raw/register/great-britain-nutrition-and-health-claims-spreadsheet-19-may-2026.xlsx --date 2026-05-19
```

Attribution, as OGL v3.0 asks: contains public sector information licensed under the Open Government Licence v3.0.

## "On hold" health claims

Claims DHSC says "may continue to be used in Great Britain" while they are still under consideration. They are not in the register, so a claim that matches no authorised register entry may still be usable if it matches one here (see `docs/notes/verified-facts.md`).

| | |
|---|---|
| Page | https://www.gov.uk/government/publications/on-hold-health-claims-on-foods |
| File | https://assets.publishing.service.gov.uk/media/5fee177dd3bf7f0897f246dc/article-13.1-on-hold-health-claims.ods |
| Release | 12 Jan 2021 (the page's "Last updated" date) |
| Downloaded | 31 Oct 2026, to `data/raw/on-hold/article-13.1-on-hold-health-claims.ods` |
| SHA-256 | `be05caee2ccc9abd3955f0dcd204d2e698b02adfb7d3c20ffc2276abfe25bb0f` |
| Size | 233,834 bytes |
| Publisher | Department of Health and Social Care |
| Licence | Open Government Licence v3.0, as for the register (same GOV.UK footer, no exception stated). © Crown copyright. |
| Snapshot | `data/snapshots/on-hold-2021-01-12.jsonl`, committed: 2,078 botanical and 17 other claims, keyed by DHSC's Claim ID, which is unique in this release |

Rebuild the snapshot from the download:

```
uv run python -m preflight.sources.on_hold data/raw/on-hold/article-13.1-on-hold-health-claims.ods --date 2021-01-12
```

The wording in this list was proposed by applicants in 2008 and DHSC warns that much of it "may not be acceptable", so it is cited as context and never offered as suggested wording (`docs/product-rules.md`, rule 2).

## ASA rulings index

| | |
|---|---|
| Source | asa.org.uk rulings pages, found through the rulings search (`preflight.sources.rulings`, see `docs/notes/rulings-corpus.md`) |
| Fetched | 31 Oct 2026, rulings published 31 Oct 2023 to 31 Oct 2026, 10 s between requests |
| Raw pages | `data/raw/rulings/` (git-ignored; 146 pages) |
| Snapshot | `data/snapshots/rulings-2026-10-31.jsonl`: the 77 in-scope rulings, metadata only (ID, date, advertiser, media, outcome, rules cited, URL, keyword topics). No ruling text, because asa.org.uk states no reuse terms (`docs/source-terms.md`). |

Rebuild the raw cache and the index:

```
uv run python -m preflight.sources.rulings fetch --from 31/10/2023 --to 31/10/2026
uv run python -m preflight.sources.rulings build --version 2026-10-31
```
