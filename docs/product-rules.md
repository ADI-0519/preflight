# Product rules

*Drafted 27 October 2026; confirmed by the founders as drafted on 31 October 2026 (task P05).*

PreFlight screens ads; it does not give legal advice. These rules keep its output honest, its evaluation clean and its customers' ads private. Changing one needs the agreement of all three founders and a dated note in the decision record.

1. **Screening, not legal advice.** Every output says so. Never say an ad "is compliant", "passes" or "is approved". The clean result is "no issues found against <sources, dated>", naming the register, CAP Code and rulings snapshot versions used.
2. **Suggested wording comes only from the register.** It is the GB register's authorised wording, quoted exactly, with its register ID. The model never writes, paraphrases or shortens claim text. If no entry matches, there is no suggestion.
3. **Every flag cites and shows.** Each flag names its source (register entry, CAP Code rule number, or ASA ruling ID and date) and shows its evidence: the transcript timestamp, or the on-screen region and frame time.
4. **A person makes the call.** The tool flags and explains; it never approves an ad, marks it ready to publish, or pushes it live.
5. **Evaluation hygiene.** Held-back ASA rulings never appear in prompts, few-shot examples, retrieval indexes or tuning. We report recall (breaches caught) and false-alarm rate on a fixed, versioned test split. Changing the split means a new version, never an edit in place.
6. **Customer ads are confidential.** No training, fine-tuning or few-shot use of customer ads. Retention is logged and enforced. Nothing customer-derived goes into the repo, notes or info-level logs. Third-party model APIs only under terms that exclude training on our inputs.
7. **Respect source terms.** Scraping, storing and redistributing the GB register, the CAP Code and asa.org.uk content follow their terms of use. What we may store, and how often we may fetch, is recorded in `docs/source-terms.md` before any scraper is built.
8. **Reconstruction hygiene.** Benchmark reconstructions are generated only from a ruling's ad-description section. A reconstruction of a held-back ruling is test data and never reaches prompts, examples or indexes.
9. **No public verdicts on unruled ads.** Demos, posts and the gallery use only reconstructions of ruled ads (branding removed, ruling ID shown), ads we made, or partners' ads shown with written consent.
10. **Standard mode only.** Anything that can carry partner or customer material goes to the Meta Model API in Standard mode, never the training-enabled Contributor mode.
