---
name: pr-handoff
description: Produce a concise evidence-based handoff for completed PreFlight work, including scope, verification, risks, and next steps.
---

# PreFlight handoff

Use this skill when a bounded task or implementation phase is complete.

Review the diff and report:

- what changed and why;
- files or modules affected;
- exact verification commands and results;
- untested paths, data, security, or product risks;
- documentation or Graphify freshness status;
- the smallest sensible next step.

Do not claim completion if required tests or product invariants are unverified. Do not commit, push, open a pull request, or deploy unless explicitly requested.
