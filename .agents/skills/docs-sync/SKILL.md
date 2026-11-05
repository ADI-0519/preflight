---
name: docs-sync
description: Synchronize PreFlight documentation with a behavior, architecture, schema, or workflow change.
---

# Documentation synchronization

Use this skill after a behavior or architecture change, not for isolated formatting or typo fixes.

Choose only the documents that own the changed information:

- `docs/architecture.md` for data flow, schema, modules and models;
- `docs/evaluation.md` for items, scoring and run records;
- `docs/product-rules.md` for user-visible behavior and invariants;
- relevant README or API documentation for user-facing setup.

Do not duplicate the same rule across documents. Update documentation only when the implementation and tests establish the behavior, and state unresolved gaps rather than presenting plans as shipped functionality.
