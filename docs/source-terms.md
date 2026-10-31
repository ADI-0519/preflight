# Source terms

What each source's terms let us fetch, store and show (`docs/product-rules.md`, rule 7). No scraper is built for a source until its row is filled in. Quotes are verbatim from the page named, on the date read.

| Source | Fetch | Store | Show or quote | Rate | Licence | Read |
|---|---|---|---|---|---|---|
| asa.org.uk (rulings) | Allowed for ruling pages. `robots.txt` disallows only `*/type/capcode/code_rule/*`, `*/type/bcapcode/code_rule/*` and `*/account/*` for all user agents. | Full pages locally under `data/raw/` (git-ignored) only. The site states no reuse terms, so copyright is reserved by default. The repo may hold short quotes of ad wording as a ruling quotes them, in the evaluation ground truth (`eval/ground_truth/`), by founders' decision of 31 Oct 2026 (`docs/notes/decisions.md`). | Ruling ID, date, advertiser, outcome, rules cited, URL and short attributed quotes. No full ruling text in the repo, the page or the video until the ASA gives permission. | No crawl delay for generic agents (`Crawl-delay: 120` for Slurp, 60 for BLEXBot and MJ12bot). In practice the server reset connections and refused new ones after bursts at 6 s spacing: use at least 10 s between requests, with back-off. | None stated. Footer: "Copyright © 2026 ASA and CAP". No Open Government Licence statement. | 31 Oct 2026 |
| gov.uk (GB nutrition and health claims register, and DHSC's "on hold" claims list) | Allowed: a single published file, downloaded once per release. `www.gov.uk/robots.txt` disallows only print views and site search for generic agents; `assets.publishing.service.gov.uk`, which serves the files, has no `robots.txt` (404). | Raw XLSX under `data/raw/register/` (git-ignored); processed snapshot committed under `data/snapshots/`. | Allowed in full with attribution, including verbatim claim wording. The attribution line is "Contains public sector information licensed under the Open Government Licence v3.0.", since the page gives no other; no use may suggest official status or endorsement. | One request per release. | Open Government Licence v3.0. Page footer: "All content is available under the Open Government Licence v3.0, except where otherwise stated"; no exception stated for this file. © Crown copyright. The same terms cover the on-hold list (`https://www.gov.uk/government/publications/on-hold-health-claims-on-foods`). | 31 Oct 2026 |

## asa.org.uk

Pages read on 31 Oct 2026:

- `https://www.asa.org.uk/robots.txt`:
  ```
  User-agent: *
   Disallow: */type/capcode/code_rule/*
   Disallow: */type/bcapcode/code_rule/*
   Disallow: */account/*
  ```
  The CAP Code rule pages are disallowed. Task P12 has to take the CAP Code text from another route, such as the published PDF or the section pages outside `code_rule/`, and record that route here.
- CAP Code route used by P12 (31 Oct 2026): the section pages `/type/non_broadcast/code_section/01.html`, `03.html`, `12.html` and `15.html`, which `robots.txt` allows, read once each with 10 s between requests. The section pages give no per-rule anchors, so each rule in the pack links to its section page. Under the same no-reuse-terms position as rulings, the pack in `data/snapshots/cap-s15-<date>.yaml` holds rule numbers and our own paraphrases only, not the Code's text.
- The footer links to accessibility, cookie policy, privacy policy, media, Cymru and unacceptable contact pages. None of them has terms of use or reuse terms. The media page has nothing on copyright or reuse.
- `sitemap.xml` lists no terms-of-use, copyright or legal page. `/general/terms-of-use.html`, `/general/terms-and-conditions.html`, `/general/legal.html`, `/general/copyright.html`, `/general/terms.html`, `/general/disclaimer.html` and `/general/legal-notice.html` all return 404.
- `/advice-and-resources/copy-advice/terms-and-conditions.html` covers only the paid Expedited Turnaround copy advice service: "All intellectual property rights in the advice and related materials remain vested in us" (9.1). It says nothing about rulings or the website.

Open questions for the founders:

- Whether to ask the ASA for written permission to store rulings and show excerpts in the demo and benchmark write-up. This needs a founder's go-ahead because it means contacting someone outside the team.
- Whether the UK text and data mining exception (CDPA s.29A) helps us. It covers non-commercial research only, so it probably does not cover a startup, but nobody has checked.
