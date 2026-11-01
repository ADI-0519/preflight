---
name: evaluation-integrity
description: Protect PreFlight evaluation validity when changing datasets, splits, metrics, replay fixtures, or evaluation code.
---

# Evaluation integrity

Use this skill when changing `eval/`, evaluation fixtures, dataset construction, scoring, metric reporting, or model replay behavior.

Check before editing:

- train, validation, and test inputs remain separated;
- no test labels or rulings leak into prompts, features, caches, or thresholds;
- replay fixtures are synthetic or explicitly approved for repository use;
- metrics remain reproducible and their denominators are visible;
- changes do not tune behavior against the held-out test set.

Run the narrowest evaluation tests first, then the normal non-live suite. Record the dataset/split, command, result, and known limitations in the handoff.
