# Decisions

One dated line per decision the founders take. Changing a product rule needs all three founders and a line here.

The P05 decisions below were taken by one founder (NEESAY) on 31 Oct 2026 and await confirmation by the other two. Until both confirm, the product rules stand as confirmed by one founder only.

- **31 Oct 2026 (P05).** Keep and reframe PreFlight. Gate 2 passed (`docs/notes/ruling-rebuildability-sample.md`) and gate 1 is unclear but has not failed (`docs/notes/hackathon-rules.md`), so there is no switch to DampTrace. The organisers' answer on gate 1 is still needed before P15.
- **31 Oct 2026 (P05).** Product rules 1–10 confirmed as drafted; `docs/product-rules.md` is no longer a draft.
- **31 Oct 2026 (P05).** Stack confirmed as in `docs/plan.md`, "Stack", with one change: the front end is React with TypeScript built by Vite, served as static files by FastAPI, in place of a single plain HTML page.
- **31 Oct 2026 (P05).** The two fully built topics wait until P13 reports how many rulings each topic has. Mushroom and magnesium are held provisionally; of the 27 rulings saved so far, 2 mention mushroom and 3 magnesium, against 20 that mention ADHD (a keyword count, not a topic classification). ADHD-claim supplements stay the hook. The choice is final when P14 freezes split v1.
- **31 Oct 2026 (P05).** Reconstruction voiceover uses a local open-source TTS in the fixture builder only; the screening path stays on Meta models.
- **31 Oct 2026 (P05).** P24 word timestamps come from a local forced aligner run over the Voice Transcribe transcript, as an optional extra; where alignment fails, the turn's start and end are kept and the evidence is marked turn-level.
- **31 Oct 2026 (P05).** Lanes have no fixed owners. Whoever claims a task becomes its issue's assignee.
- **31 Oct 2026 (P05).** The team will not ask the ASA for permission to store and show ruling excerpts for now. What we store and show stays within `docs/source-terms.md`.
The P14 decisions below were confirmed by all three founders on 31 Oct 2026.

- **31 Oct 2026 (P14).** Split v1 covers all in-scope topics rather than two, because mushroom (7) and magnesium (5) are too small to fill a test split (`docs/notes/rulings-corpus.md`).
- **31 Oct 2026 (P14).** The evaluation ground truth may hold short quotes of ad wording as ASA rulings quote them (799 claims in split v1), committed to the repo. Full ruling text stays out of the repo (`docs/source-terms.md`).
- **31 Oct 2026 (P14).** PreFlight's scope widens from health claims to every CAP Code breach in a supplement ad, including misleading and comparative claims under section 3. A24-1251814 (Viridian, section 3 only) stays in the v1 test split. The CAP rule pack, claim extraction (P26) and the checker (P27) must follow; split v1 cites 13 rules the pack lacks (2.1, 2.3, 3.3, 3.17, 3.40, 3.42, 3.50, 4.4, 13.7, 13.9, 15.3, 15.3.1, 15.3.2), added in P16. Where the register has no wording for a breach, no fix is suggested (`docs/product-rules.md`, rule 2).
- **31 Oct 2026 (P14).** One founder checks the ground truth of a split; for v1 that is NEESAY. Whoever reads the test split's ground truth does not write prompts or few-shot examples (`docs/product-rules.md`, rule 5).
- **31 Oct 2026 (P14).** Split v1 is frozen: 25 positives and 5 negatives in dev, 49 positives and 10 negatives in test, 799 breaching claims, every item checked. Any change to the lists or the ground truth means v2.
- **1 Nov 2026 (P26/P27 implementation).** Claim extraction validates every model-provided evidence reference against the supplied transcript, on-screen text and visual tracks, then assigns local claim IDs. Checking uses deterministic register shortlisting and a dependency-free precedent index with a held-back-ruling refusal gate; the judge may select sources and an authorised register ID, but only snapshot data can create source references or suggested wording. Full screening-level `verify_sources` now validates ruling IDs and dates against the rulings snapshot.
