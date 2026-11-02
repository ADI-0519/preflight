---
name: code-change-verification
description: Verify a PreFlight code, test, build, or dependency change with the smallest relevant checks and report evidence.
---

# Code change verification

Use this skill when a change affects runtime code, tests, dependencies, configuration, or build behavior.

1. Inspect the diff and identify the narrowest affected test files.
2. Run focused tests first, then `uv run ruff check` and `uv run pytest -m "not live"` when the change is substantive.
3. Run `python scripts/verify_agent_setup.py` when repository instructions or skill files changed.
4. Report commands, pass/fail results, skipped live checks, and any unverified risk. Do not claim success from inspection alone.

Do not install packages, contact external services, commit, push, or deploy unless the user explicitly authorizes it.
