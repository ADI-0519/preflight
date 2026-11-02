"""Check repository-local agent instructions without requiring network access."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SKILLS = {
    "code-change-verification",
    "preflight-product-invariants",
    "evaluation-integrity",
    "docs-sync",
    "pr-handoff",
}


def main() -> int:
    failures: list[str] = []

    agents = ROOT / "AGENTS.md"
    if not agents.is_file():
        failures.append("missing AGENTS.md")

    skills_root = ROOT / ".agents" / "skills"
    found = {
        path.parent.name
        for path in skills_root.glob("*/SKILL.md")
        if path.is_file()
    }
    missing = REQUIRED_SKILLS - found
    if missing:
        failures.append(f"missing skills: {', '.join(sorted(missing))}")

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    if "graphify-out/" not in gitignore:
        failures.append(".gitignore does not exclude graphify-out/")
    if ".env" not in gitignore:
        failures.append(".gitignore does not exclude .env files")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    print(f"OK: {len(REQUIRED_SKILLS)} repository skills, AGENTS.md, and secret/output exclusions verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
