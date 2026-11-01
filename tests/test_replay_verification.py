import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_screening_replay.py"


def test_verification_runs_without_credentials_and_preserves_outputs(tmp_path):
    env = {k: v for k, v in os.environ.items() if k not in ("META_API_KEY", "BASETEN_API_KEY", "OPENAI_API_KEY")}
    out = tmp_path / "replay"
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--out", str(out)], cwd=ROOT, env=env, capture_output=True, text=True,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "synthetic_replay" and manifest["verified"]
    assert manifest["claims"] > 0 and manifest["flags"] > 0
    assert len(manifest["source_fingerprint"]) == 64
    assert len(manifest["limitations"]) == 4
    assert set(manifest["artifacts"]) == {"report.html", "screening.json"}
    assert "not a live model run" in (out / "report.html").read_text(encoding="utf-8")
    # Re-running must not overwrite an artifact a reviewer may already be inspecting.
    again = subprocess.run(
        [sys.executable, str(SCRIPT), "--out", str(out)], cwd=ROOT, env=env, capture_output=True, text=True,
    )
    assert again.returncode == 1 and "FileExistsError" in again.stderr
