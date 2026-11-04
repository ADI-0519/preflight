"""Explicit network-blocked browser-test server; never selected by the normal app."""

import json
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

import httpx
from openai import OpenAI
from test_api import AGENT, MEDIA, NoPrecedents, recorded_screener, replay_ingest
from test_script import ScriptSpark

from preflight.agent.draft import render_draft
from preflight.api import Settings
from preflight.api.app import create_app as application
from preflight.models import Image, Models, Sam, Spark, Store, VoiceTranscribe
from preflight.schema import Screening, StageRun


class BrowserScriptSpark(ScriptSpark):
    def ask(self, text, **config):
        time.sleep(0.25)
        return super().ask(text, **config)


def rendered_recordings(models, precedents, directory, align=None):
    recorded = recorded_screener(models, precedents, directory, align)

    def screen(draft, screening_id, previous_id):
        render_draft(draft, directory / "renders")
        return recorded(draft, screening_id, previous_id)

    return screen


@contextmanager
def replay_clients(directory):
    def refuse(request):
        raise AssertionError("Browser replay must not contact a model provider")

    with httpx.Client(transport=httpx.MockTransport(refuse)) as http:
        with OpenAI(api_key="replay-only", http_client=http, max_retries=0) as api:
            store = Store(Path(__file__).parent / "fixtures/models", "replay")
            script = any((directory / f"media{suffix}").exists() for suffix in (".txt", ".md"))
            spark = Spark(store, api)
            if script:
                source = next(directory.glob("media.*")).read_text(encoding="utf-8-sig")
                spark = BrowserScriptSpark(empty=source.startswith("SUPER: Orange flavour"),
                                           broken=source.startswith("VO: Synthetic incomplete"))
            yield Models(spark, VoiceTranscribe(store, "replay-only", http=http),
                         Sam(store, api), Image(store, api), None)


def create_app():
    # A short private root also keeps FFmpeg below Windows path limits.
    root = Path(tempfile.mkdtemp(prefix="pf-web-"))
    demos = root / "demos"
    demos.mkdir()
    entries = []
    flagged = Screening.model_validate_json((AGENT / "round0.json").read_text(encoding="utf-8"))
    clean = Screening.model_validate_json((AGENT / "round1.json").read_text(encoding="utf-8"))
    incomplete = clean.model_copy(update={"stages": (StageRun(stage="check", status="failed"),)})
    for identifier, title, screening in [
        ("flagged", "Synthetic replay · flagged", flagged),
        ("clean", "Synthetic replay · no flags", clean),
        ("incomplete", "Synthetic replay · incomplete", incomplete),
    ]:
        (demos / f"{identifier}.json").write_text(screening.model_dump_json(), encoding="utf-8")
        entries.append({"id": identifier, "title": title, "kind": "synthetic",
                        "screening": f"{identifier}.json", "media": "captions.mp4"})
    (demos / "captions.mp4").write_bytes((MEDIA / "captions.mp4").read_bytes())
    (demos / "items.json").write_text(json.dumps(entries), encoding="utf-8")
    results = root / "results"
    results.mkdir()
    app = application(
        Settings(root=root / "uploads"), demo_root=demos, results_root=results,
        models_factory=replay_clients, precedents_factory=NoPrecedents,
        ingester=replay_ingest, draft_screener=rendered_recordings,
    )
    app.state.verification_label = (
        "Network-blocked synthetic replay. Responses are recordings, not results from your uploaded ad."
    )
    return app
