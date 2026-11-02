import socket
import wave
from pathlib import Path

import pytest

from preflight.evidence.align import letters, mms_aligner
from preflight.evidence.transcribe import MIN_SCORE, transcribe
from preflight.ingest import Ingested
from preflight.models import Store, Turn, from_env
from preflight.models.clients import TRANSCRIBE
from preflight.schema import Ad

FIXTURES = Path(__file__).parent / "fixtures" / "models"
SPEECH = FIXTURES / "media" / "speech.wav"
TRANSCRIPT = "Bright Leaf Daily Leaf Daily D vitamin D contributes to the normal"


class Stub:
    def __init__(self, turns: list[Turn]):
        self.turns, self.calls = turns, 0

    def transcribe(self, wav: bytes) -> list[Turn]:
        self.calls += 1
        return self.turns


def silent(path: Path, seconds: float) -> Path:
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(bytes(round(seconds * 16000) * 2))
    return path


def ingested(audio: Path | None, duration: float = 10.0) -> Ingested:
    ad = Ad(content_hash="0" * 64, media="video", width=320, height=180, duration=duration, fps=2.0)
    return Ingested(
        ad=ad, source=Path("ad.mp4"), audio=audio, video=Path("ad.mp4"), rate=2.0, threshold=0.3, frames=(),
        keyframes=(),
    )


def fake(spans, score=0.9):
    def align(pcm, rate, words):
        assert len(spans) == len(words)
        return spans, score

    return align


@pytest.fixture
def models(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network used in a replay test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setenv("META_API_KEY", "dummy")
    return from_env(Store(FIXTURES, "replay"))


def test_replay_turn_fallback(models):
    segments, run = transcribe(ingested(SPEECH, 3.04), models.transcribe, align=None)
    assert [(s.segment_id, s.turn, s.text, s.start, s.end, s.timing) for s in segments] == [
        ("segment-0", 0, TRANSCRIPT, 0.22, 2.54, "turn")
    ]
    assert (run.stage, run.status, run.model) == ("transcribe", "done", TRANSCRIBE)


def test_word_timing_with_fake_aligner(tmp_path):
    wav = silent(tmp_path / "a.wav", 10)
    voice = Stub([Turn(1000, 5000, "Buy now. Daily D vitamin works well", "A")])
    # sentence end after "now.", a 0.5 s gap after "D"
    spans = [(0.3, 0.6), (0.7, 1.0), (1.4, 1.6), (1.65, 1.7), (2.2, 2.5), (2.55, 2.9), (2.95, 3.3)]
    segments, _ = transcribe(ingested(wav), voice, align=fake(spans))
    assert [(s.segment_id, s.text, s.timing) for s in segments] == [
        ("segment-0", "Buy now.", "word"), ("segment-1", "Daily D", "word"), ("segment-2", "vitamin works well", "word")
    ]
    # the slice starts 0.25 s before the turn, so 0.75 s on the ad's clock; ends run on by TAIL
    assert [(round(s.start, 2), round(s.end, 2)) for s in segments] == [(1.05, 1.9), (2.15, 2.6), (2.95, 4.2)]


def test_low_score_falls_back(tmp_path):
    voice = Stub([Turn(1000, 2000, "Buy now", "A")])
    aligner = fake([(0, 0.1), (0.2, 0.3)], MIN_SCORE / 2)
    segments, _ = transcribe(ingested(silent(tmp_path / "a.wav", 10)), voice, align=aligner)
    assert [(s.start, s.end, s.timing) for s in segments] == [(1.0, 2.0, "turn")]


def test_aligner_error_falls_back(tmp_path):
    def broken(pcm, rate, words):
        raise RuntimeError("no alignment")

    voice = Stub([Turn(1000, 2000, "Buy now", "A"), Turn(3000, 4000, "Again", "A")])
    segments, run = transcribe(ingested(silent(tmp_path / "a.wav", 10)), voice, align=broken)
    assert [(s.turn, s.start, s.end, s.timing) for s in segments] == [(0, 1.0, 2.0, "turn"), (1, 3.0, 4.0, "turn")]
    assert run.status == "done"


def test_unalignable_words_take_neighbour_span(tmp_path):
    voice = Stub([Turn(1000, 5000, "1000 Daily 1000 users 100%", "A")])
    spans = [None, (0.5, 0.9), None, (1.2, 1.5), None]
    segments, _ = transcribe(ingested(silent(tmp_path / "a.wav", 10)), voice, align=fake(spans))
    # the whole turn is one phrase; its edges are the turn edges where the neighbours are missing, with no tail
    assert [(s.start, s.end) for s in segments] == [(1.0, 5.0)]


def test_unalignable_word_between_phrases(tmp_path):
    voice = Stub([Turn(1000, 5000, "Daily 1000. users", "A")])
    spans = [(0.5, 0.9), None, (1.0, 1.5)]
    segments, _ = transcribe(ingested(silent(tmp_path / "a.wav", 10)), voice, align=fake(spans))
    # the first segment's tail stops where the next starts
    assert [(s.text, round(s.start, 2), round(s.end, 2)) for s in segments] == [
        ("Daily 1000.", 1.25, 1.75), ("users", 1.75, 2.4)
    ]


def test_times_stay_inside_the_ad(tmp_path):
    voice = Stub([Turn(500, 2000, "Buy now", "A")])
    aligner = fake([(0.0, 0.5), (1.5, 9.0)])
    segments, _ = transcribe(ingested(silent(tmp_path / "a.wav", 2.0), 2.0), voice, align=aligner)
    assert segments[-1].end == 2.0


def test_words_with_digits_are_not_aligned():
    assert [letters(w) for w in ["53p", "3,000mg", "D3", "Lion's", "gummies."]] == ["", "", "", "lion's", "gummies"]


def test_no_audio_skipped():
    voice = Stub([])
    segments, run = transcribe(ingested(None), voice, align=None)
    assert (segments, run.status, voice.calls) == ([], "skipped", 0)


def test_empty_wav(tmp_path):
    voice = Stub([])
    segments, run = transcribe(ingested(silent(tmp_path / "a.wav", 0)), voice)
    assert (segments, run.status, voice.calls) == ([], "done", 0)


def test_no_turns(tmp_path):
    segments, run = transcribe(ingested(silent(tmp_path / "a.wav", 1)), Stub([]), align=None)
    assert (segments, run.status) == ([], "done")


def test_turn_text_split_on_punctuation(tmp_path):
    voice = Stub([Turn(1000, 4000, "Buy now. Is it good? Yes! really", "A"), Turn(5000, 6000, "no stops here", "B")])
    segments, _ = transcribe(ingested(silent(tmp_path / "a.wav", 10)), voice, align=None)
    assert [(s.segment_id, s.turn, s.text, s.start, s.end) for s in segments] == [
        ("segment-0", 0, "Buy now.", 1.0, 4.0), ("segment-1", 0, "Is it good?", 1.0, 4.0),
        ("segment-2", 0, "Yes!", 1.0, 4.0), ("segment-3", 0, "really", 1.0, 4.0),
        ("segment-4", 1, "no stops here", 5.0, 6.0),
    ]


def test_mms_aligner_on_fixture():
    pytest.importorskip("torchaudio")
    with wave.open(str(SPEECH)) as f:
        pcm = f.readframes(f.getnframes())
    words = TRANSCRIPT.split()
    # the turn is 0.22 s to 2.54 s, padded as the stage pads it
    spans, score = mms_aligner()(pcm[:round(2.79 * 16000) * 2], 16000, words)
    assert len(spans) == len(words) and 0 < score <= 1
    assert all(a[0] <= a[1] <= b[0] for a, b in zip(spans, spans[1:], strict=False))
    assert 0.1 <= spans[0][0] and spans[-1][1] <= 2.8
    other = mms_aligner()(pcm, 16000, "the quick brown fox jumps over a lazy dog near the river".split())
    assert other[1] < score


def test_audio_other_than_mono_16_bit_is_refused(tmp_path):
    path = tmp_path / "stereo.wav"
    with wave.open(str(path), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(bytes(16000 * 4))
    with pytest.raises(ValueError, match="mono 16-bit"):
        transcribe(ingested(path), Stub([]), align=None)
