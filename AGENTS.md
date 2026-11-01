# PreFlight agent guidance

## Mission

PreFlight helps advertisers identify possible Meta policy issues before submission. Preserve the distinction between evidence-backed screening and final platform enforcement.

## Non-negotiable product rules

- Do not claim that an ad is approved, compliant, safe, or guaranteed to pass review.
- Every user-visible flag must include evidence and source provenance.
- Use only policy wording and source material present in the repository; do not invent citations or register wording.
- Keep Contributor mode separate from customer or partner data. Use synthetic fixtures for tests and demos.
- Never place API keys, raw customer media, or downloaded partner data in source, logs, fixtures, or commits.

## Working rules

- For architecture questions, query `graphify-out/graph.json` before broad file reads.
- Use `docs/plan.md` for roadmap scope, `docs/product-rules.md` for product behavior, and `docs/notes/decisions.md` for durable decisions.
- Keep changes bounded to the requested phase. State non-goals before implementation when the change crosses schema, model, evidence, evaluation, or API boundaries.
- Prefer deterministic scripts and existing project tooling over asking the model to reproduce checklists.
- Do not commit, push, deploy, call external services, or use credentials without explicit user approval.

## Verification

The normal local checks are:

```text
uv run ruff check
uv run pytest -m "not live"
python scripts/verify_agent_setup.py
```

For schema, evidence, model, evaluation, or API changes, run the narrowest relevant tests first, then the normal checks above. Report exact commands and results.

## Skill routing

- Runtime, test, build, or dependency changes: use `code-change-verification`.
- Product wording, schema, policy source, or evidence behavior: use `preflight-product-invariants`.
- Dataset splits, metrics, replay fixtures, or evaluation code: use `evaluation-integrity`.
- Behavior or architecture changes: use `docs-sync`.
- Task completion or handoff: use `pr-handoff`.
