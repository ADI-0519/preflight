import re
import subprocess
import tempfile
from pathlib import Path

from preflight.eval.check_reconstructions import carried, words
from preflight.eval.reconstruct import (
    HEIGHT,
    ROOT,
    Builder,
    Scene,
    ShotList,
    _escape,
    _font,
    _wrap,
    canvas,
    label_filter,
)

KINDS = ("music", "speech_only", "small_text", "split_cuts", "compressed")
STRESS_DIR = ROOT / "data" / "raw" / "stress"
# about 40% of the 34-point text a reconstruction's captions start at
SMALL = 14
LINE_SECONDS = 1.0
# a music bed sits about 12 dB under the voiceover
UNDER_DB = 12
# a re-uploaded social clip: 480 lines, a few hundred kilobits a second
LOW_HEIGHT, VIDEO_KBPS, AUDIO_KBPS, JPEG_QUALITY = 480, 300, 48, 25


class Skip(Exception):
    pass


def holds(text: str, claim: str) -> bool:
    return carried(claim, words(text)) != "missing"


def speech_only(shots: ShotList, claims: list[str]) -> ShotList:
    if shots.format != "video":
        raise Skip("a still has no soundtrack")
    scenes, moved = [], False
    for s in shots.scenes:
        spoken = [line for line in s.on_screen_text if any(holds(line, c) for c in claims)]
        moved = moved or bool(spoken)
        scenes.append(s.model_copy(update={
            "on_screen_text": [line for line in s.on_screen_text if line not in spoken],
            "voiceover": " ".join([s.voiceover.strip(), *spoken]).strip(),
        }))  # fmt: skip
    if not moved:
        raise Skip("no on-screen line carries a claim")
    return shots.model_copy(update={"scenes": scenes})


def _span(tokens: list[str], claim: str) -> tuple[int, int] | None:
    # the shortest run of the line's words that still carries the claim
    found = [(i, j) for i in range(len(tokens)) for j in range(i + 1, len(tokens) + 1)
             if holds(" ".join(tokens[i:j]), claim)]  # fmt: skip
    return min(found, key=lambda s: s[1] - s[0], default=None)


def split_line(line: str, claims: list[str]) -> tuple[str, str] | None:
    held = [c for c in claims if holds(line, c)]
    tokens = line.split()
    # a cut mid-claim for each claim, with pieces alternating between the scenes, puts each claim's halves apart
    cuts = sorted({(i + j) // 2 for i, j in filter(None, (_span(tokens, c) for c in held)) if j - i > 1})
    if not cuts:
        return None
    pieces = [tokens[a:b] for a, b in zip([0, *cuts], [*cuts, len(tokens)], strict=True)]
    return " ".join(w for p in pieces[0::2] for w in p), " ".join(w for p in pieces[1::2] for w in p)


def split_cuts(shots: ShotList, claims: list[str]) -> tuple[ShotList, list[int], list[str]]:
    scenes, stills, split = [], [], False
    for i, s in enumerate(shots.scenes):
        halves = {line: split_line(line, claims) for line in s.on_screen_text if any(holds(line, c) for c in claims)}
        halves = {line: h for line, h in halves.items() if h}
        if not halves:
            scenes.append(s)
            stills.append(i)
            continue
        split = True
        first = [halves[line][0] if line in halves else line for line in s.on_screen_text]
        second = [halves[line][1] for line in s.on_screen_text if line in halves]
        half = s.duration_seconds / 2
        scenes += [
            s.model_copy(update={"on_screen_text": first, "duration_seconds": half}),
            s.model_copy(update={"on_screen_text": second, "duration_seconds": half, "voiceover": ""}),
        ]
        stills += [i, i]
    if not split:
        raise Skip("no claim line splits at a word boundary")
    # claims a single scene still shows whole, reported with the item
    whole = [c for c in claims if any(holds(" ".join(s.on_screen_text), c) for s in scenes)]
    return shots.model_copy(update={"scenes": scenes}), stills, whole


def small_text(shots: ShotList) -> ShotList:
    if shots.format != "video":
        return shots
    # each line gets its second on screen, so a scene lasts at least that long
    return shots.model_copy(update={"scenes": [
        s.model_copy(update={"duration_seconds": max(s.duration_seconds, LINE_SECONDS * len(s.on_screen_text))})
        for s in shots.scenes
    ]})  # fmt: skip


def small_overlay(scene: Scene, fmt: str) -> str:
    font, step = _font(), int(SMALL * 1.3)
    filters = canvas()
    if fmt == "video":
        # one line at a time in the lower left corner, about a second each, with no box behind it
        for i, line in enumerate(scene.on_screen_text):
            rows = _wrap(line, width=110)
            for j, row in enumerate(rows):
                y = HEIGHT - 30 - step * (len(rows) - 1 - j)
                filters.append(
                    f"drawtext={font}expansion=none:text='{_escape(row)}':fontsize={SMALL}:fontcolor=white:x=20:y={y}:"
                    f"enable='between(t,{i * LINE_SECONDS},{(i + 1) * LINE_SECONDS})'"
                )
    else:
        # a still shows every line at once, small, in the lower left corner
        rows = [r for line in scene.on_screen_text for r in _wrap(line, width=110)]
        for j, row in enumerate(rows):
            y = HEIGHT - 30 - step * (len(rows) - 1 - j)
            filters.append(
                f"drawtext={font}expansion=none:text='{_escape(row)}':fontsize={SMALL}:fontcolor=white:x=20:y={y}"
            )
    filters.append(label_filter())
    return ",".join(filters)


def music_bed(seconds: float) -> str:
    # a synthetic chord with a pulse, made by ffmpeg: no licensed audio
    chord = "0.3*sin(2*PI*110*t)+0.2*sin(2*PI*220*t)+0.15*sin(2*PI*277.18*t)+0.15*sin(2*PI*329.63*t)"
    return f"aevalsrc='({chord})*(0.6+0.4*sin(2*PI*2*t))':s=24000:d={seconds:.2f}"


def music_gain(speech_db: float, music_db: float) -> float:
    return round(speech_db - UNDER_DB - music_db, 1)


def _ffmpeg(*args: str) -> str:
    return subprocess.run(["ffmpeg", "-y", "-hide_banner", *args], check=True, capture_output=True, text=True).stderr


def mean_db(path: Path) -> float:
    report = _ffmpeg("-i", str(path), "-af", "volumedetect", "-f", "null", "-")
    return float(re.search(r"mean_volume: (-?[\d.]+) dB", report)[1])


def _seconds(path: Path) -> float:
    probe = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]
    return float(subprocess.run(probe, check=True, capture_output=True, text=True).stdout)


def render(kind: str, source: Path, out: Path, claims: list[str], builder: Builder) -> list[Path]:
    shots = ShotList.model_validate_json((source / "shotlist.json").read_text(encoding="utf-8"))
    stills = [source / f"scene{i}.png" for i in range(len(shots.scenes))]
    plain = [source / "reconstruction.mp4"] if shots.format == "video" else sorted(source.glob("reconstruction*.png"))
    out.mkdir(parents=True, exist_ok=True)
    if kind == "speech_only":
        builder.assemble(speech_only(shots, claims), out, stills)
    elif kind == "split_cuts":
        cut, order, whole = split_cuts(shots, claims)
        builder.assemble(cut, out, [stills[i] for i in order])
        (out / "whole_claims.txt").write_text("\n".join(whole), encoding="utf-8")
    elif kind == "small_text":
        builder.assemble(small_text(shots), out, stills, overlay=lambda s: small_overlay(s, shots.format))
    elif kind == "music":
        if shots.format != "video":
            raise Skip("a still has no soundtrack")
        with tempfile.TemporaryDirectory() as tmp:
            bed = Path(tmp) / "bed.wav"
            _ffmpeg("-f", "lavfi", "-i", music_bed(_seconds(plain[0])), str(bed))
            gain = music_gain(mean_db(plain[0]), mean_db(bed))
            _ffmpeg("-i", str(plain[0]), "-i", str(bed), "-filter_complex",
                    f"[1:a]volume={gain}dB[m];[0:a][m]amix=inputs=2:normalize=0:duration=first[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
                    str(out / "reconstruction.mp4"))  # fmt: skip
    elif kind == "compressed":
        for p in plain:
            if p.suffix == ".mp4":
                _ffmpeg("-i", str(p), "-vf", f"scale=-2:{LOW_HEIGHT}", "-c:v", "libx264", "-b:v", f"{VIDEO_KBPS}k",
                        "-maxrate", f"{VIDEO_KBPS}k", "-bufsize", f"{2 * VIDEO_KBPS}k", "-c:a", "aac",
                        "-b:a", f"{AUDIO_KBPS}k", str(out / p.name))  # fmt: skip
            else:
                _ffmpeg("-i", str(p), "-vf", f"scale=-2:{LOW_HEIGHT}", "-q:v", str(JPEG_QUALITY),
                        str(out / f"{p.stem}.jpg"))  # fmt: skip
    else:
        raise ValueError(f"unknown stress kind {kind}")
    return [out / "reconstruction.mp4"] if (out / "reconstruction.mp4").exists() else sorted(
        p for p in out.glob("reconstruction*") if p.suffix in (".png", ".jpg"))  # fmt: skip
