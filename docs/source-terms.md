# Source terms

This file records, for each outside source, what its terms allow PreFlight to fetch, store and show, and how often it may be fetched. A source is read only after its entry here is filled in. Quotations are verbatim from the page named, on the date given.

## Summary

| Source | Licence | In the repository | Local only (git-ignored) | Fetching |
|---|---|---|---|---|
| GB nutrition and health claims register | Open Government Licence v3.0 | Processed snapshot with verbatim claim wording | The downloaded XLSX | One download per release |
| DHSC "on hold" health claims list | Open Government Licence v3.0 | Processed snapshot | The downloaded ODS | One download per release |
| asa.org.uk: rulings | None stated; copyright reserved | Ruling metadata; short attributed quotes of ad wording in the ground truth | Full ruling pages | At least 10 s between requests, with back-off |
| asa.org.uk: CAP Code | None stated; copyright reserved | Rule numbers and paraphrased summaries | Nothing | Section pages only, 10 to 12 s between requests |
| Meta Model API | Meta Model API terms of service | Nothing | Model response cache | Not applicable |
| Baseten Model APIs (development only) | Baseten terms and conditions | Nothing | Response cache and experiment files | Not applicable |

## GB nutrition and health claims register

Read 31 October 2026.

- **Licence.** Open Government Licence v3.0. The publication page footer reads "All content is available under the Open Government Licence v3.0, except where otherwise stated", and the page states no exception for the register file. © Crown copyright.
- **Use.** The licence allows copying, publishing and adapting with attribution, so the register's claim wording may be shown in full and quoted verbatim. Any use must not suggest official status or endorsement. The page gives no attribution wording of its own, so PreFlight uses the licence's: "Contains public sector information licensed under the Open Government Licence v3.0."
- **Stored.** The raw XLSX stays in `data/raw/register/`. The processed snapshot `data/snapshots/register-2026-05-19.jsonl` is committed. Its release date, download URL and checksum are in [data/README.md](../data/README.md).
- **Fetching.** The file is a single published download, fetched once per release. `www.gov.uk/robots.txt` disallows only print views and site search for generic agents. `assets.publishing.service.gov.uk`, which serves the file, has no `robots.txt` (it returns 404).

## DHSC "on hold" health claims list

Read 31 October 2026. The list is published at `https://www.gov.uk/government/publications/on-hold-health-claims-on-foods`.

- **Licence.** Open Government Licence v3.0, under the same GOV.UK footer and with no exception stated. © Crown copyright.
- **Stored.** The raw ODS stays in `data/raw/on-hold/`. The processed snapshot `data/snapshots/on-hold-2021-01-12.jsonl` is committed.
- **Use.** The proposed wording in this list came from applicants, and DHSC warns that much of it "may not be acceptable". PreFlight therefore cites an on-hold entry as context and never offers its wording as a suggestion.
- **Fetching.** One download per release, as for the register.

## asa.org.uk

Read 31 October 2026. Rulings and the CAP Code are both published on asa.org.uk and share its terms.

### Terms

The site states no terms of use or reuse terms, so copyright is reserved by default. The footer reads "Copyright © 2026 ASA and CAP" and carries no Open Government Licence statement. Several checks found nothing more:

- The footer links to accessibility, cookie policy, privacy policy, media, Cymru and unacceptable contact pages. None of them sets out terms of use or reuse terms, and the media page says nothing on copyright or reuse.
- `sitemap.xml` lists no terms-of-use, copyright or legal page. `/general/terms-of-use.html`, `/general/terms-and-conditions.html`, `/general/legal.html`, `/general/copyright.html`, `/general/terms.html`, `/general/disclaimer.html` and `/general/legal-notice.html` all return 404.
- `/advice-and-resources/copy-advice/terms-and-conditions.html` covers only the paid Expedited Turnaround copy advice service ("All intellectual property rights in the advice and related materials remain vested in us", 9.1). It says nothing about rulings or the website.

`robots.txt` disallows the CAP Code rule pages and account pages for every user agent:

```
User-agent: *
 Disallow: */type/capcode/code_rule/*
 Disallow: */type/bcapcode/code_rule/*
 Disallow: */account/*
```

It sets no crawl delay for generic agents. It sets `Crawl-delay: 120` for Slurp and 60 for BLEXBot and MJ12bot.

### Rulings

- **Stored.** Full ruling pages are kept only in `data/raw/rulings/`, which git ignores. The committed snapshots in `data/snapshots/rulings-<date>.jsonl` hold metadata only: ruling ID, date, advertiser, media, outcome, rules cited, URL and keyword topics. The evaluation ground truth in `eval/ground_truth/` may hold short quotes of ad wording as a ruling quotes them.
- **Shown.** Ruling ID, date, advertiser, outcome, rules cited, URL and short attributed quotes. No full ruling text appears in the repository or the web page unless the ASA gives permission.
- **Fetching.** Ruling pages are allowed by `robots.txt`. In practice the server reset connections and refused new ones after bursts of requests 6 s apart, so the fetcher (`preflight.sources.rulings`) waits at least 10 s between requests and backs off exponentially after a failure.

### CAP Code

- **Route.** The rule pages are disallowed by `robots.txt`, so the rule pack is read from the section pages under `/type/non_broadcast/code_section/`, which are allowed. Sections 1, 2, 3, 4, 12, 13 and 15 were read on 31 October 2026, with 10 to 12 s between requests, and section 3 was read again on 1 November 2026. The section pages carry no per-rule anchors, so each rule in the pack links to its section page.
- **Stored.** The pack in `data/snapshots/cap-<date>.yaml` holds rule numbers and PreFlight's own paraphrased summaries, never the Code's text. The section pages carry no edition date; the pack records the latest amendment any page mentions.

### Open questions

- Written permission from the ASA would allow ruling pages to be stored and excerpts shown more widely. It has not been requested.
- The UK text and data mining exception (Copyright, Designs and Patents Act 1988, s.29A) covers non-commercial research only. It probably does not cover a commercial product, and nobody has checked further.

## Meta Model API

Read 31 October 2026 at `https://dev.meta.ai/docs/pricing-rate-limits` and `https://dev.meta.ai/docs/file-handling`, and on 4 November 2026 at `https://dev.meta.ai/legal/terms-of-service`.

- **Training.** "In Standard mode, you pay standard prices and your content is not used to train Meta models." Contributor mode grants "permission to use your content — the prompts, code, files, and context you send, plus the model responses you get back — to train future Meta models". Section 5.1 of the terms of service (dated 9 October 2026) excludes content submitted to Standard Services from training Meta models. PreFlight calls every model in Standard mode. "Contributor mode isn't available for Muse Voice Transcribe."
- **Uploaded files.** "Uploaded files don't expire, so stored data only grows until you remove it." PreFlight's model client sets `expires_after` on every upload, within the allowed range of "3600 (1 hour) to 2592000 (30 days)", and deletes the file as soon as the call ends.
- **Responses.** The API stores responses by default and offers retrieval and deletion by ID; the pages read do not say how long a response is kept. PreFlight sends `store=False` on every Muse Spark call. A live check on 2 November 2026 confirmed that a response created with `store=False` cannot be retrieved afterwards.
- **Zero data retention.** The pricing page offers it ("Zero data retention (ZDR) is priced at parity with Standard mode") but does not describe how to enable it.
- **Stored by PreFlight.** Model answers are cached locally by content hash under `data/cache/`, which git ignores. The cache is not committed.

The training exclusion is contractual. It does not by itself establish that Meta retains nothing.

## Baseten Model APIs

Read 2 November 2026. Baseten hosts the open-weights Muse Spark Open model used in one development experiment on first-pass triage. Production screening never calls it.

- [Terms and conditions, section 6.3](https://www.baseten.co/terms-and-conditions/) exclude customer content from training, fine-tuning and model development.
- [Security practices](https://www.baseten.co/security-practices/) describe no persistent storage of inputs or outputs for synchronous Model APIs. Logging, integrations and configurations a customer selects can change that, asynchronous queues may keep inputs for up to 72 hours, and security metadata is kept under separate rules. Both documents are dated 15 September 2026.
- The experiment uses only development reconstructions and synthetic inputs. Its local response cache and output files are git-ignored.
