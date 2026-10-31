# GB register: what the 19 May 2026 release contains

Read 31 Oct 2026 for P11. Source, licence and hash in `data/README.md`; loader in `src/preflight/sources/register.py`.

## Counts

| | Entries |
|---|---|
| Health claims, authorised | 267 (6 of them asterisked: authorised on proprietary data, also listed in the annex) |
| Health claims, non-authorised | 2,082 |
| Nutrition claims (all authorised) | 30 |
| **Authorised in total** | **297** |
| **All entries** | **2,379** |

The health claims sheet has 2,555 data rows: 2,349 entries plus 206 continuation rows that carry only an extra scientific-opinion link in column F (the spreadsheet merges cells for these). The loader attaches each continuation row's link to the entry above it.

## Statuses

The spreadsheet uses exactly three values: `Authorised for use in Great Britain`, the same with a trailing `*`, and `Non-authorised`. It has no "on hold" status. The EU's on-hold botanical claims are not in this register at all, so a botanical claim (for example on a mushroom extract) finds no authorised wording here. The loader rejects any other status value, so a new one in a future release fails loudly instead of being misfiled.

## IDs are not stable in the source, so we define our own

The `Entry Id` column is not an ID. It holds EFSA reference numbers, often several per row (`"152, 157, 215"`), sometimes `not applicable`, and 189 values repeat across rows. We keep them as `efsa_ids` and do not key on them.

`register_id` is `gbhc-` plus the first 12 hex characters of the SHA-256 of the row's claim type, substance, claim, conditions of use, health relationship and Entry Id, exactly as they appear in the spreadsheet (joined with U+001F). Those six columns are the smallest set that is unique across the release: dropping the health relationship leaves 149 colliding pairs, all non-authorised near-duplicates. Nutrition claims get `gbnc-` plus the hash of the claim name. The loader refuses to build a snapshot if two entries get the same ID.

The ID stays the same across releases as long as none of those six cells changes. Status is deliberately left out, so a claim that moves from non-authorised to authorised keeps its ID. We could not compare against an earlier release: GOV.UK serves only the current file, and the Internet Archive was offline on 31 Oct 2026. GOV.UK's change notes since 2021 describe only additions (one claim each in 2024 and 2026, two in 2025), so existing rows appear not to be edited between releases. Rebuilding from the next release and diffing the IDs will confirm this.

## Wording and markup

Rule 2 quotes the register's wording exactly. 86 claim cells (10 authorised) and some substance cells contain HTML markup, for example `<p class="tbl-txt">Vitamin D helps to reduce the risk of falling…</p>`, and 5 authorised claims use entities such as `&lt;name of all used non-digestible carbohydrates&gt;`. Each entry therefore carries two fields:

- `wording_source`: the cell exactly as published, byte for byte.
- `wording`: the same text with HTML tags removed and entities decoded, and no other change (whitespace, punctuation and case are untouched). This is the text to quote. The two differ for 13 authorised claims and are identical for the other 284.

Four authorised claims contain line breaks inside the cell; both fields keep them.

## Not loaded

- The nutrition claims sheet has no claim type, Entry Id or references; those fields are empty for `gbnc-` entries.
- The separate annex file (health claims authorised on proprietary data) is not loaded. Its six claims are already in the main sheet, marked with `*`, and `proprietary` is set on them.
