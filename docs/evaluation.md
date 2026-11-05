# Evaluation

The [evaluation protocol](plan.md#evaluation-protocol-contract-for-p14-and-p31)
defines item construction, split separation, leakage protection, claim matching,
metrics and registered runs. The [generated results](../results/final.md) and
[run registry](../results/runs.csv) contain the recorded figures.

## Baseline

The [keyword baseline](../src/preflight/eval/baseline.py) makes no model calls.
It reads the reconstruction shot-list text or the team-written ad's source lines,
splits them into sentences, and applies two checks:

- A sentence naming a register substance and a benefit term, without containing
  the normalised wording of a shortlisted authorised entry, is flagged under
  CAP 15.1 and 15.1.1.
- Disease, condition and cure terms outside recognised authorised wording are
  flagged under CAP 15.6 and 15.6.2.

It uses the same scoring harness as the model pipeline. It receives source text
directly rather than recovering text from media, so it avoids perception errors.
That is one advantage of this baseline setup; it does not establish that the
entire comparison is controlled for every possible difference.

## Interpretation and provenance

Finding every claim is a design objective, not a measured guarantee. The registered
carried-claim recall with a matching rule is 334/530. Twenty negative ads are too
few to establish a dependable real-world false-alarm rate. Unmatched flags on
positive ads need separate adjudication because the ASA annotations are not exhaustive.

The first 79-item test attempt did not register because of a validation failure.
After the documented source-reference fix, the registered run replayed the saved
answers rather than judging the items again. See the **4 Nov 2026 (P33)** entry in
the [decision log](notes/decisions.md). The description of a single test run in the
README refers to that recorded model-answer set, not a claim that no failed
execution or subsequent replay occurred.

Replay requires the corresponding recordings and input/source assets. A public
clone does not include every ignored cache or source page, and fresh live calls
need not produce identical outputs. Historical commit IDs and metadata fingerprints
precede the repository transfer; the decision log records the identity normalisation
and its limits. Neither the transfer nor the README update reran the benchmark.

For local deletion timing and provider-retention boundaries, see
[retention and errors](api.md#retention-and-errors). The default expiry is 24 hours;
physical deletion depends on the running sweep and active-job handling.
