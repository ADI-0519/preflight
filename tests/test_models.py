import json
import os
import socket
from pathlib import Path
from types import SimpleNamespace as NS

import httpx
import openai
import pytest
from dotenv import load_dotenv

from preflight.models import CacheMiss, Sam, Spark, Store, VoiceTranscribe, from_env
from preflight.models.clients import parse_sam
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
    monkeypatch.setenv("BASETEN_API_KEY", "dummy")
    monkeypatch.setenv("GLIMMER_MODEL", "glimmer-fixture")
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
    cls = {429: openai.RateLimitError, 503: openai.InternalServerError}.get(code, openai.BadRequestError)
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


def test_transcribe_replay(replay):
    turns = replay.transcribe.transcribe(WAV)
    assert len(turns) == 1
    assert (turns[0].start_ms, turns[0].end_ms) == (220, 2540)
    assert "vitamin D" in turns[0].text


def test_transcribe_refuses_non_wav(replay):
    with pytest.raises(ValueError, match="WAV"):
        replay.transcribe.transcribe(b"ID3 not a wav file")


def test_sam_image_replay(replay):
    r = replay.sam.segment("black rectangle", image=FRAME)
    (frame,) = r.frames
    (obj,) = frame.objects
    assert (obj.id, obj.box) == (0, (40.0, 60.0, 279.0, 119.0))
    assert 0.5 < obj.confidence <= 1
    assert obj.mask.startswith("x=0;y=0;")
    assert "mask" not in repr(obj)


def test_sam_video_replay(replay):
    r = replay.sam.segment("black rectangle", video=VIDEO)
    assert [f.index for f in r.frames] == list(range(15))
    assert all(len(f.objects) == 1 and f.objects[0].id == 0 for f in r.frames)
    assert r.usage["video_frames_processed"] == 50


def test_sam_empty_response_is_valid(tmp_path):
    api = NS(responses=NS(stream=lambda **kw: EmptyStream()))
    assert Sam(Store(tmp_path), api).segment("text", image=FRAME).frames == []


def test_sam_two_objects_in_one_frame_replay(replay):
    (frame,) = replay.sam.segment("black rectangle", image=(MEDIA / "boxes.png").read_bytes()).frames
    assert sorted((o.id, o.box) for o in frame.objects) == [
        (0, (180.0, 80.0, 289.0, 149.0)), (1, (20.0, 40.0, 119.0, 99.0))
    ]
    assert all("box;" not in o.mask for o in frame.objects)


def test_sam_unparsed_output_raises(tmp_path):
    with pytest.raises(ValueError, match="frame 0"):
        parse_sam("<0f>0<|box;x1=1;y1=2;x2=3;y2=4;w=9;h=9|> stray")


def test_image_generate_replay(replay):
    png = replay.image.generate("a plain white tub labelled Brightleaf Daily D")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_glimmer_replay(replay):
    r = replay.glimmer.ask("Say hello.", prompt_version=PV)
    assert r.text == "Hello."


class EmptyStream:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        return iter(())

    def get_final_response(self):
        return NS(model="sam-3.1", usage=None)


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

    attempts = []

    def handler(request):
        attempts.append(request)
        if len(attempts) == 1:
            return httpx.Response(429, headers={"Retry-After": "1"})
        return httpx.Response(200, json={"turns": [{"startMs": 0, "endMs": 5, "transcript": "hi"}]})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    turns = VoiceTranscribe(Store(tmp_path), "dummy", http, sleep=sleeps.append).transcribe(WAV)
    assert turns[0].text == "hi"
    assert len(attempts) == 2


def test_other_client_errors_are_not_retried(tmp_path):
    sleeps = []
    api = FakeApi(fail=[status_error(400)])
    with pytest.raises(openai.BadRequestError):
        Spark(Store(tmp_path), api, sleeps.append).ask("hello", prompt_version=PV, effort="low")
    assert api.requests == 1
    assert sleeps == []


def test_server_errors_and_dropped_connections_are_retried(tmp_path):
    sleeps = []
    request = httpx.Request("POST", "https://example.invalid")
    api = FakeApi(fail=[status_error(503), openai.APIConnectionError(request=request)])
    spark = Spark(Store(tmp_path), api, sleeps.append)
    assert spark.ask("hello", prompt_version=PV, effort="low").text == "ok"
    assert api.requests == 3
    assert sleeps == [1.0, 2.0]


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
    monkeypatch.setenv("BASETEN_API_KEY", SENTINEL)
    monkeypatch.setenv("GLIMMER_MODEL", "glimmer-fixture")
    models = from_env(Store(tmp_path))
    assert SENTINEL not in repr(models)
    models.spark.api = FakeApi()
    models.spark.ask("hello", prompt_version=PV, effort="low")
    http = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"turns": []})),
    )
    models.transcribe.http = http
    models.transcribe.transcribe(WAV)
    files = list(tmp_path.rglob("*.json"))
    assert len(files) == 2
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


@pytest.mark.live
@need("META_API_KEY")
def test_transcribe_live(tmp_path):
    turns = from_env(Store(tmp_path)).transcribe.transcribe(WAV)
    assert "vitamin" in " ".join(t.text for t in turns).lower()


def test_spark_respond_caches_and_replays(tmp_path):
    item = NS(model_dump=lambda exclude_none: {"type": "function_call", "name": "screen_ad", "call_id": "c1"})
    seen = []

    def create(**kwargs):
        seen.append(kwargs)
        return NS(status="completed", model="muse-spark-1.3", output=[item], output_text="", usage=None)

    api = NS(responses=NS(create=create))
    tools = [{"type": "function", "name": "screen_ad"}]
    ask = [{"type": "message", "role": "user", "content": "hi"}]
    kwargs = {"tools": tools, "prompt_version": PV, "effort": "low", "instructions": "be brief"}
    first = Spark(Store(tmp_path), api).respond(ask, **kwargs)
    again = Spark(Store(tmp_path), api).respond(ask, **kwargs)
    assert len(seen) == 1
    assert seen[0]["instructions"] == "be brief"
    assert first.calls == again.calls == [{"type": "function_call", "name": "screen_ad", "call_id": "c1"}]
    with pytest.raises(CacheMiss):
        Spark(Store(tmp_path, "replay"), api).respond([*ask, ask[0]], **kwargs)


@pytest.mark.live
@need("META_API_KEY")
def test_sam_live(tmp_path):
    r = from_env(Store(tmp_path)).sam.segment("black rectangle", image=FRAME)
    assert r.frames[0].objects


@pytest.mark.live
@need("META_API_KEY")
def test_image_live(tmp_path):
    models = from_env(Store(tmp_path))
    png = models.image.generate("a plain white tub labelled Brightleaf Daily D")
    assert png[:4] == b"\x89PNG"
    assert models.image.edit(FRAME, "make the background blue")[:4] == b"\x89PNG"


@pytest.mark.live
@need("META_API_KEY", "BASETEN_API_KEY", "GLIMMER_MODEL")
def test_glimmer_live(tmp_path):
    assert from_env(Store(tmp_path)).glimmer.ask("Reply with one word.", prompt_version=PV).text
