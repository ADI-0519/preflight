"""Produce an inspectable synthetic screening without credentials or network access.

Uses the same video plus separate speech fixture as record_model_fixtures.screen.
This verifies replay contracts and rendering, not model quality or precedent retrieval.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import httpx
from openai import OpenAI

from preflight.ingest import ingest
from preflight.models import Image, Models, Sam, Spark, Store, VoiceTranscribe
from preflight.models.store import digest
from preflight.pipeline import SNAPSHOTS, screen
from preflight.report import render_html
from preflight.schema import NOTICE, Screening, verify_sources

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "models"
REPLAY_NOTICE = (
    "Synthetic replay verification: recorded responses, not a live model run. "
    "Separate speech fixture; no precedent retrieval; no accuracy claim."
)


class NoPrecedents:
    """The synthetic recording was made without retrieval of ruling text."""

    version = SNAPSHOTS.rulings

    def top(self, query: str, k: int = 3) -> list:
        return []


def refuse_network(request: httpx.Request) -> httpx.Response:
    raise RuntimeError("network is disabled for replay verification")


def source_fingerprint() -> str:
    """Identify the actual working sources, including uncommitted integration fixes."""
    paths = [ROOT / "pyproject.toml", ROOT / "uv.lock", Path(__file__).resolve()]
    paths += list((ROOT / "src").rglob("*.py"))
    paths += list((ROOT / "prompts").glob("*.txt"))
    paths += list((ROOT / "data" / "snapshots").glob("*"))
    paths += list(FIXTURES.rglob("*.json"))
    fingerprint = hashlib.sha256()
    for path in sorted(p for p in paths if p.is_file()):
        fingerprint.update(path.relative_to(ROOT).as_posix().encode() + b"\0")
        fingerprint.update(bytes.fromhex(digest(path)))
    return fingerprint.hexdigest()


def run_replay(out: Path) -> Screening:
    out.mkdir(parents=True, exist_ok=False)
    clip, speech = FIXTURES / "media" / "captions.mp4", FIXTURES / "media" / "speech.wav"
    done = ingest(clip, out_root=out / "media")
    # Both fixture model recordings use the already sampled 2-fps clip and this
    # separate WAV. Preserve those exact bytes so replay keys match the recording.
    done = done.model_copy(update={"video": clip, "audio": speech})
    store = Store(FIXTURES, "replay")
    with httpx.Client(transport=httpx.MockTransport(refuse_network)) as http:
        with OpenAI(api_key="replay-only", http_client=http, max_retries=0) as api:
            models = Models(
                spark=Spark(store, api), transcribe=VoiceTranscribe(store, "replay-only", http=http),
                sam=Sam(store, api), image=Image(store, api), glimmer=None,
            )
            screening = screen(done, models, NoPrecedents(), "synthetic-replay", align=None)
    (out / "screening.json").write_text(screening.model_dump_json(indent=2), encoding="utf-8")
    page = render_html(screening, done.frames[0].path.parent.parent)
    page = page.replace("<body>", f'<body><p class="notice">{REPLAY_NOTICE}</p>', 1)
    (out / "report.html").write_text(page, encoding="utf-8")
    verify_sources(screening)
    expected = {"transcribe", "on_screen", "regions", "claims", "check"}
    if {s.stage for s in screening.stages if s.status == "done"} != expected:
        raise RuntimeError("replay did not complete all five stages; inspect screening.json")
    if not screening.claims or not screening.flags:
        raise RuntimeError("replay did not produce the recorded claims and flags")
    loaded = Screening.model_validate_json((out / "screening.json").read_text(encoding="utf-8"))
    verify_sources(loaded)
    if loaded != screening or NOTICE not in (out / "report.html").read_text(encoding="utf-8"):
        raise RuntimeError("saved screening or report did not preserve the result and notice")
    return screening


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="new output directory; existing paths are refused")
    args = parser.parse_args(argv)
    try:
        screening = run_replay(args.out)
    except Exception as error:
        # No automatic cache-mode fallback: a changed prompt must fail, never call a model.
        print(f"Replay verification failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.strip()
    dirty = bool(subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout)
    manifest = {
        "mode": "synthetic_replay", "verified": True, "git_sha": head, "dirty": dirty,
        "source_fingerprint": source_fingerprint(),
        "inputs": {name: digest(FIXTURES / "media" / name) for name in ("captions.mp4", "speech.wav")},
        "snapshots": screening.snapshots.model_dump(),
        "stages": [stage.model_dump() for stage in screening.stages],
        "claims": len(screening.claims), "flags": len(screening.flags),
        "limitations": [
            "Recorded model responses; no live inference or accuracy measurement.",
            "Video and separate audio fixture assembled explicitly; not a single uploaded ad.",
            "No precedent text retrieved; only snapshot-reference validation is exercised.",
            "Forced alignment disabled; transcript uses turn timings.",
        ],
        "artifacts": {name: digest(args.out / name) for name in ("screening.json", "report.html")},
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Synthetic replay verified: {len(screening.claims)} claims, {len(screening.flags)} flags")
    print(args.out / "report.html")
    print(args.out / "manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
