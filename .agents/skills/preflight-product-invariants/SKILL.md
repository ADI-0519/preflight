---
name: preflight-product-invariants
description: Check PreFlight product wording, policy evidence, source provenance, and data-boundary invariants when screening behavior changes.
---

# PreFlight product invariants

Use this skill when changing schema, claims, checks, evidence, policy sources, model output handling, or user-visible screening results.

- Preserve the distinction between screening and final Meta enforcement.
- Do not use approval, compliance, safety, or guaranteed-pass language.
- Require evidence and source provenance for every user-visible flag.
- Keep exact policy/register wording grounded in repository sources; do not invent policy text.
- Keep Contributor mode and synthetic fixtures separate from customer or partner data.

Inspect `docs/product-rules.md` and the relevant source/tests before editing. Add or update focused tests for every changed invariant, and report any behavior that remains intentionally unimplemented.
