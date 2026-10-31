# Source terms

What each source's terms let us fetch, store and show (`docs/product-rules.md`, rule 7). No scraper is built for a source until its row is filled in. Quotes are verbatim from the page named, on the date read.

| Source | Fetch | Store | Show or quote | Rate | Licence | Read |
|---|---|---|---|---|---|---|
| asa.org.uk (rulings) | Allowed for ruling pages. `robots.txt` disallows only `*/type/capcode/code_rule/*`, `*/type/bcapcode/code_rule/*` and `*/account/*` for all user agents. | Locally under `data/raw/` (git-ignored) only. The site states no reuse terms, so copyright is reserved by default. | Ruling ID, date, advertiser, outcome, rules cited, URL and short attributed quotes. No full ruling text in the repo, the page or the video until the ASA gives permission. | No crawl delay for generic agents (`Crawl-delay: 120` for Slurp, 60 for BLEXBot and MJ12bot). In practice the server reset connections and refused new ones after bursts at 6 s spacing: use at least 10 s between requests, with back-off. | None stated. Footer: "Copyright © 2026 ASA and CAP". No Open Government Licence statement. | 31 Oct 2026 |

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
- The footer links to accessibility, cookie policy, privacy policy, media, Cymru and unacceptable contact pages. None of them has terms of use or reuse terms. The media page has nothing on copyright or reuse.
- `sitemap.xml` lists no terms-of-use, copyright or legal page. `/general/terms-of-use.html`, `/general/terms-and-conditions.html`, `/general/legal.html`, `/general/copyright.html`, `/general/terms.html`, `/general/disclaimer.html` and `/general/legal-notice.html` all return 404.
- `/advice-and-resources/copy-advice/terms-and-conditions.html` covers only the paid Expedited Turnaround copy advice service: "All intellectual property rights in the advice and related materials remain vested in us" (9.1). It says nothing about rulings or the website.

Open questions for the founders:

- Whether to ask the ASA for written permission to store rulings and show excerpts in the demo and benchmark write-up. This needs a founder's go-ahead because it means contacting someone outside the team.
- Whether the UK text and data mining exception (CDPA s.29A) helps us. It covers non-commercial research only, so it probably does not cover a startup, but nobody has checked.
