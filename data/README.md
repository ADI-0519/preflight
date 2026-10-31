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
