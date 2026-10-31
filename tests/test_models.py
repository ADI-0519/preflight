import json
import os
import socket
from pathlib import Path
from types import SimpleNamespace as NS

import httpx
import openai
import pytest
from dotenv import load_dotenv

from preflight.models import CacheMiss, Spark, Store, from_env
from preflight.models.store import check_model

load_dotenv()

FIXTURES = Path(__file__).parent / "fixtures" / "models"
MEDIA = FIXTURES / "media"
FRAME, WAV, VIDEO = (MEDIA / "frame.png").read_bytes(), (MEDIA / "speech.wav").read_bytes(), MEDIA / "ad.mp4"
SPEECH = "Brightleaf Daily D. Vitamin D contributes to the normal function of the immune system."
SCHEMA = {
    "type": "object",
    "properties": {"claims": {"type": "array", "items": {"type": "string"}}},
    "required": ["claims"],
    "additionalProperties": False,
}
PV = "fixture-1"
SENTINEL = "sk-sentinel-4f2a9c"


@pytest.fixture
def replay(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network used in a replay test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setenv("META_API_KEY", "dummy")
    return from_env(Store(FIXTURES, "replay"))


def response(text="ok", model="muse-spark-1.3"):
    usage = {"input_tokens": 1, "output_tokens": 1}
    return NS(model=model, status="completed", output_text=text, usage=NS(model_dump=lambda: usage))


class FakeApi:
    def __init__(self, fail=()):
        self.fail, self.requests, self.uploads, self.deleted = list(fail), 0, [], []
        self.responses = NS(create=self.create)
        self.files = NS(create=self.upload, delete=self.deleted.append)

    def create(self, **kwargs):
        self.requests += 1
        if self.fail:
            raise self.fail.pop(0)
        return response()

    def upload(self, **kwargs):
        self.uploads.append(kwargs)
        return NS(id="file-1")


def status_error(code, headers=None):
    request = httpx.Request("POST", "https://example.invalid")
    r = httpx.Response(code, headers=headers, request=request)
    cls = openai.RateLimitError if code == 429 else openai.BadRequestError
    return cls("failed", response=r, body=None)


def test_spark_text_structured_replay(replay):
    r = replay.spark.ask(
        f"List every claim in this script.\n\n{SPEECH}", prompt_version=PV, effort="low", schema=SCHEMA
    )
    assert r.model == "muse-spark-1.3"
    assert r.data == {"claims": ["Vitamin D contributes to the normal function of the immune system."]}
    assert r.usage["output_tokens_details"]["reasoning_tokens"] > 0


def test_spark_image_replay(replay):
    r = replay.spark.ask("Transcribe all text visible in this image.", prompt_version=PV, effort="low", image=FRAME)
    assert "Brightleaf Daily D" in r.text
    assert r.data is None


def test_spark_video_replay(replay):
    r = replay.spark.ask(
        "List each on-screen text with its start and end time in seconds.", prompt_version=PV, effort="low", video=VIDEO
    )
    assert "Brightleaf Daily D" in r.text


def test_second_identical_call_served_from_cache(tmp_path):
    api = FakeApi()
    spark = Spark(Store(tmp_path), api)
    first = spark.ask("hello", prompt_version=PV, effort="low")
    second = spark.ask("hello", prompt_version=PV, effort="low")
    assert api.requests == 1
    assert first == second


def test_changed_inputs_miss_the_cache(tmp_path):
    api = FakeApi()
    spark = Spark(Store(tmp_path), api)
    spark.ask("hello", prompt_version=PV, effort="low", image=b"\x00")
    spark.ask("hello", prompt_version="fixture-2", effort="low", image=b"\x00")
    spark.ask("hello", prompt_version=PV, effort="high", image=b"\x00")
    spark.ask("hello", prompt_version=PV, effort="low", image=b"\x01")
    assert api.requests == 4


@pytest.mark.parametrize(
    "bad", [NS(**{**vars(response("{")), "status": "completed"}), NS(**{**vars(response()), "status": "incomplete"})]
)
def test_bad_spark_answer_not_cached(tmp_path, bad):
    api = FakeApi()
    api.responses = NS(create=lambda **kw: NS(**vars(bad), incomplete_details=None))
    with pytest.raises((RuntimeError, json.JSONDecodeError)):
        Spark(Store(tmp_path), api).ask("hello", prompt_version=PV, effort="low", schema=SCHEMA)
    assert not list(tmp_path.rglob("*.json"))


def test_replay_miss_raises(tmp_path):
    api = FakeApi()
    spark = Spark(Store(tmp_path, "replay"), api)
    with pytest.raises(CacheMiss, match="muse-spark-1.3"):
        spark.ask("hello", prompt_version=PV, effort="low")
    assert api.requests == 0


def test_contributor_model_refused(tmp_path):
    with pytest.raises(ValueError, match="contributor"):
        check_model("muse-spark-1.3-contributor")
    with pytest.raises(ValueError, match="contributor"):
        Store(tmp_path).fetch("muse-spark-1.3-contributor", {}, lambda: {})
    api = FakeApi()
    api.create = lambda **kw: response(model="muse-spark-1.3-contributor")
    api.responses = NS(create=api.create)
    with pytest.raises(ValueError, match="contributor"):
        Spark(Store(tmp_path), api).ask("hello", prompt_version=PV, effort="low")
    assert not list(tmp_path.rglob("*.json"))


def test_rate_limit_retried_then_succeeds(tmp_path):
    sleeps = []
    api = FakeApi(fail=[status_error(429, {"Retry-After": "3"}), status_error(429)])
    spark = Spark(Store(tmp_path), api, sleeps.append)
    assert spark.ask("hello", prompt_version=PV, effort="low").text == "ok"
    assert api.requests == 3
    assert sleeps == [3.0, 2.0]


def test_other_errors_not_retried(tmp_path):
    sleeps = []
    api = FakeApi(fail=[status_error(400)])
    with pytest.raises(openai.BadRequestError):
        Spark(Store(tmp_path), api, sleeps.append).ask("hello", prompt_version=PV, effort="low")
    assert api.requests == 1
    assert sleeps == []


def test_rate_limit_gives_up_after_five_attempts(tmp_path):
    api = FakeApi(fail=[status_error(429)] * 6)
    with pytest.raises(openai.RateLimitError):
        Spark(Store(tmp_path), api, lambda s: None).ask("hello", prompt_version=PV, effort="low")
    assert api.requests == 5


def test_upload_has_expiry_and_is_deleted(tmp_path):
    api = FakeApi()
    Spark(Store(tmp_path), api).ask("hello", prompt_version=PV, effort="low", video=VIDEO)
    assert api.uploads[0]["expires_after"] == {"anchor": "created_at", "seconds": 3600}
    assert api.deleted == ["file-1"]

    failing = FakeApi(fail=[RuntimeError("boom")])
    with pytest.raises(RuntimeError, match="boom"):
        Spark(Store(tmp_path), failing).ask("goodbye", prompt_version=PV, effort="low", video=VIDEO)
    assert failing.deleted == ["file-1"]


def test_key_not_in_repr_or_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("META_API_KEY", SENTINEL)
    models = from_env(Store(tmp_path))
    assert SENTINEL not in repr(models)
    models.spark.api = FakeApi()
    models.spark.ask("hello", prompt_version=PV, effort="low")
    files = list(tmp_path.rglob("*.json"))
    assert len(files) == 1
    assert all(SENTINEL not in f.read_text(encoding="utf-8") for f in files)


def test_cache_entry_is_readable_json(tmp_path):
    Spark(Store(tmp_path), FakeApi()).ask("hello", prompt_version=PV, effort="low")
    (path,) = tmp_path.rglob("*.json")
    entry = json.loads(path.read_text(encoding="utf-8"))
    assert set(entry) == {"key", "response"}
    assert "hello" not in path.read_text(encoding="utf-8")
    assert not list(tmp_path.rglob("*.tmp"))


def need(*names):
    return pytest.mark.skipif(
        not all(os.environ.get(n) for n in names), reason=f"{' and '.join(names)} not set"
    )


@pytest.mark.live
@need("META_API_KEY")
def test_spark_live(tmp_path, monkeypatch):
    models = from_env(Store(tmp_path))
    r = models.spark.ask("Reply with the single word: ready", prompt_version=PV, effort="low")
    assert r.model == "muse-spark-1.3"
    assert "ready" in r.text.lower()
    monkeypatch.setattr(models.spark.api.responses, "create", lambda **kw: pytest.fail("second request sent"))
    assert models.spark.ask("Reply with the single word: ready", prompt_version=PV, effort="low") == r
