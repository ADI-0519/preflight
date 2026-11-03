import argparse
import re
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from preflight import check as judge
from preflight import claims as extraction
from preflight.check.precedents import load_precedents
from preflight.eval.check_reconstructions import carried, words
from preflight.eval.claim_recall import WORK
from preflight.eval.reconstruct import (
    HEIGHT,
    OUT_DIR,
    ROOT,
    Builder,
    Scene,
    ShotList,
    _escape,
    _font,
    _wrap,
    canvas,
    ensure_voice,
    label_filter,
)
from preflight.eval.registry import RESULTS, Metric, register, revision, snapshot_text, write_rows
from preflight.eval.run import WORKERS, joined, kept, saved, screen_item, show, vote_tag
from preflight.eval.score import caught, metric, metrics, per_ad, score_item
from preflight.eval.split import RULING_ID, load_ground_truth, load_split
from preflight.models import from_env
from preflight.pipeline import SNAPSHOTS

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
        (p for p in out.glob("reconstruction*") if p.suffix in (".png", ".jpg")), key=card)  # fmt: skip


def card(path: Path) -> tuple[int, str]:
    # cards are read in order, and a name sort would put reconstruction-1 before reconstruction
    return len(path.stem), path.stem


def flips(truth, plain: list, stress: list) -> tuple[bool, bool, int, int]:
    carried_claims = kept(truth) or [True] * len(truth.claims)
    before = caught(truth.claims, plain, truth.item_id).with_rule
    after = caught(truth.claims, stress, truth.item_id).with_rule
    pairs = [(b, a) for b, a, k in zip(before, after, carried_claims, strict=True) if k]
    return (any(before) and not any(after), any(after) and not any(before),
            sum(b and not a for b, a in pairs), sum(a and not b for b, a in pairs))  # fmt: skip


def main() -> None:
    parser = argparse.ArgumentParser(description="Screen harder renders of the dev positives and register the run.")
    parser.add_argument("kind", choices=KINDS)
    parser.add_argument("--baseline", required=True, metavar="RUN_ID", help="the plain dev run screened the same way")
    parser.add_argument("--samples", type=int, choices=[1, judge.VOTE_SAMPLES], default=judge.SAMPLES)
    parser.add_argument("--judge-prompt", default=judge.PROMPT_VERSION, help="a candidate judge prompt")
    parser.add_argument("--claims-prompt", default=extraction.PROMPT_VERSION, help="a candidate claims prompt")
    parser.add_argument("--render-only", action="store_true")
    args = parser.parse_args()
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is not on PATH")
    # rule 5: dev only, and only the ruled ads, since a variant is drawn from the reconstruction's own shot list
    split = load_split("v2")
    truths = [t for t in (load_ground_truth("v2", i) for i in split.dev if RULING_ID.match(i)) if t.label == "positive"]
    # the builder only draws and speaks here; it never calls a model
    builder = Builder(client=False, voice=ensure_voice())
    paths, skipped = {}, {}
    for t in truths:
        out = STRESS_DIR / args.kind / t.item_id
        # a render already made is reused, so the single and voting runs screen the same bytes
        if made := sorted((p for p in out.glob("reconstruction*") if p.suffix in (".mp4", ".png", ".jpg")), key=card):
            paths[t.item_id] = [p for p in made if p.suffix == ".mp4"] or made
            continue
        try:
            paths[t.item_id] = render(args.kind, OUT_DIR / t.item_id, out, [c.claim for c in t.claims], builder)
        except Skip as e:
            skipped[t.item_id] = str(e)
            shutil.rmtree(out, ignore_errors=True)
        print(f"{t.item_id}: {skipped.get(t.item_id, 'rendered')}", flush=True)
    if args.render_only:
        return
    base_row, plain, _ = saved(args.baseline)
    if base_row["split"] != "v2" or base_row["part"] != "dev":
        raise SystemExit(f"{args.baseline} is not a v2 dev run")
    sha = revision("dev")
    applied = [t for t in truths if t.item_id in paths]
    precedents = {t.item_id: load_precedents(SNAPSHOTS.rulings, "v2", t.item_id) for t in applied}
    models = from_env()
    created = datetime.now(UTC)
    run_id = f"stress-{args.kind}-{created:%Y%m%dT%H%M%S}"
    (WORK / run_id).mkdir(parents=True)
    began = time.monotonic()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        done = list(pool.map(lambda t: screen_item(
            t, models, precedents[t.item_id], run_id, None, args.judge_prompt, args.samples, 0, paths[t.item_id],
            args.claims_prompt,
        ), applied))  # fmt: skip
    seconds = time.monotonic() - began

    rows, before, after, flipped = [], [], [], []
    for t, (score, screenings, usd) in zip(applied, done, strict=True):
        plain_score = score_item(t, plain[t.item_id], kept(t))
        ad_lost, ad_gained, c_lost, c_gained = flips(t, plain[t.item_id], screenings)
        flipped.append((ad_lost, ad_gained, c_lost, c_gained))
        failed = sorted({r.stage for s in screenings for r in s.stages if r.status == "failed"})
        incomplete = any(not any(r.stage == "check" and r.status == "done" for r in s.stages) for s in screenings)
        rows.append(asdict(score) | {
            "kind": args.kind, "skipped": "", "media": len(screenings), "failed": " ".join(failed),
            "incomplete_check": incomplete, "cost_usd": round(usd, 5), "plain_caught": plain_score.caught,
            "plain_caught_carried": plain_score.caught_carried, "ad_lost": ad_lost, "ad_gained": ad_gained,
            "claims_lost": c_lost, "claims_gained": c_gained, "baseline": args.baseline,
        })  # fmt: skip
        before.append(plain_score)
        after.append(score)
        failure = f", FAILED {' '.join(failed)}" if failed else ""
        print(f"{t.item_id}: {score.caught_carried} of {score.carried} carried claims caught, plain "
              f"{plain_score.caught_carried}{failure}", flush=True)  # fmt: skip
    # a skipped item is listed, so it is never read as a catch or a miss
    rows += [{"item_id": i, "kind": args.kind, "skipped": why, "baseline": args.baseline} for i, why in skipped.items()]
    write_rows(RESULTS / "runs" / f"{run_id}.csv", rows)
    if any(r.get("failed") or r.get("incomplete_check") for r in rows):
        raise SystemExit(f"{run_id}: stages failed or checks did not finish, so the run is not registered")

    screenings = [s for _, ss, _ in done for s in ss]
    run_metrics = [
        *metrics(after),
        per_ad("plain_ad_recall", before, lambda i: i.caught > 0),
        metric("plain_claim_recall_carried", before, lambda i: i.caught_carried, lambda i: i.carried),
        Metric("ads_lost", sum(f[0] for f in flipped), len(applied)),
        Metric("ads_gained", sum(f[1] for f in flipped), len(applied)),
        Metric("claims_lost", sum(f[2] for f in flipped), sum(i.carried for i in before)),
        Metric("claims_gained", sum(f[3] for f in flipped), sum(i.carried for i in before)),
        Metric("items_skipped", len(skipped), len(truths)),
        Metric("screen_cost_usd", round(sum(r["cost_usd"] for r in rows if not r["skipped"]), 4), len(applied)),
        Metric("screen_wall_seconds", round(seconds, 1), len(applied)),
    ]
    register({
        "run_id": run_id, "created_at": created.isoformat(timespec="seconds"), "git_sha": sha, "split": "v2",
        "part": "dev", "stage": "stress", "model": joined(screenings, lambda r: r.model),
        "prompt": joined(screenings, lambda r: r.prompt) + vote_tag(args.samples, 0),
        "effort": joined(screenings, lambda r: r.effort and f"{r.stage}={r.effort}"),
        "snapshots": snapshot_text(SNAPSHOTS),
    }, run_metrics)  # fmt: skip
    show(run_id, run_metrics)


if __name__ == "__main__":
    main()
