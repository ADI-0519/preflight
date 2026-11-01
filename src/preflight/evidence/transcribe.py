import io
import re
import wave
from typing import Literal

from preflight.evidence.align import Aligner, Span, mms_aligner
from preflight.ingest import Ingested
from preflight.models import Turn, VoiceTranscribe
from preflight.models.clients import TRANSCRIBE
from preflight.schema import Segment, StageRun

# a gap this long between aligned words starts a new segment
GAP = 0.3
# audio around a turn, so a word the transcriber clipped is still in the slice
PAD = 0.25
# the aligner ends a word before its sound fades, so word-timed segments run on this long
TAIL = 0.15
# see docs/notes/word-timing-check.md
MIN_SCORE = 0.35
SENTENCE_END = re.compile(r"[.!?][\"')\]]*$")


def phrases(words: list[str], spans: list[Span] | None) -> list[range]:
    out, first = [], 0
    for i, word in enumerate(words):
        last = i == len(words) - 1
        if last or SENTENCE_END.search(word) or (spans is not None and spans[i + 1][0] - spans[i][1] >= GAP):
            out.append(range(first, i + 1))
            first = i + 1
    return out


def fill(spans: list[Span | None], start: float, end: float) -> list[Span] | None:
    if all(s is None for s in spans):
        return None
    out: list[Span] = []
    for i, s in enumerate(spans):
        if s is None:
            before = out[-1][1] if out else start
            after = next((t[0] for t in spans[i + 1:] if t is not None), end)
            s = (before, max(after, before))
        out.append(s)
    return out


def clip(t: float, duration: float) -> float:
    return min(max(t, 0.0), duration)


def bounds(turn: Turn, duration: float) -> Span:
    start = clip(turn.start_ms / 1000, duration)
    return start, max(clip(turn.end_ms / 1000, duration), start)


def align_turn(
    aligner: Aligner, pcm: bytes, rate: int, duration: float, turn: Turn, words: list[str]
) -> list[Span] | None:
    start, end = bounds(turn, duration)
    lo, hi = max(start - PAD, 0.0), min(end + PAD, duration)
    try:
        spans, score = aligner(pcm[round(lo * rate) * 2:round(hi * rate) * 2], rate, words)
    except Exception:
        # an alignment that cannot run costs word timing, not the transcript
        return None
    if score < MIN_SCORE:
        return None
    spans = [None if s is None else (clip(s[0] + lo, duration), clip(s[1] + lo, duration)) for s in spans]
    return fill(spans, start, end)


def transcribe(
    done: Ingested, voice: VoiceTranscribe, align: Aligner | None | Literal["mms"] = "mms"
) -> tuple[list[Segment], StageRun]:
    if done.audio is None:
        return [], StageRun(stage="transcribe", status="skipped")
    run = StageRun(stage="transcribe", status="done", model=TRANSCRIBE)
    wav = done.audio.read_bytes()
    with wave.open(io.BytesIO(wav)) as f:
        rate, frames = f.getframerate(), f.getnframes()
        pcm = f.readframes(frames)
    if frames == 0:
        return [], run
    duration = frames / rate
    turns = voice.transcribe(wav)
    if align == "mms" and turns:
        align = mms_aligner()
    found: list[tuple[int, str, float, float, str]] = []
    for n, turn in enumerate(turns):
        words = turn.text.split()
        if not words:
            continue
        spans = align_turn(align, pcm, rate, duration, turn, words) if align else None
        for part in phrases(words, spans):
            text = " ".join(words[i] for i in part)
            if spans is None:
                found.append((n, text, *bounds(turn, duration), "turn"))
            else:
                start = spans[part[0]][0]
                found.append((n, text, start, max(spans[part[-1]][1], start), "word"))
    found.sort(key=lambda f: (f[2], f[0]))
    for i, (n, text, start, end, timing) in enumerate(found):
        if timing == "word":
            stop = found[i + 1][2] if i + 1 < len(found) else duration
            found[i] = (n, text, start, max(min(end + TAIL, stop), end), timing)
    segments = [
        Segment(segment_id=f"segment-{i}", turn=n, text=text, start=start, end=end, timing=timing)
        for i, (n, text, start, end, timing) in enumerate(found)
    ]
    return segments, run
