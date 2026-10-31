import math
import re
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor

from preflight.ingest import Ingested, run
from preflight.models import Sam
from preflight.models.clients import SAM
from preflight.schema import Region, StageRun, Track

# SAM returns nothing for text prompts such as "caption", so captions are found as the boxes they sit behind
PROMPTS = ("label", "bottle", "dark rectangle", "person")
PROMPT_VERSION = "regions-2"
# an id absent for this many sampled frames in a row starts a new track
GAP = 2
# SAM keeps one id across back-to-back captions, so an edge moving this share of the frame starts a new track
JUMP = 0.05


def slug(prompt: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", prompt.lower()).strip("-")


def pixel_box(box: tuple[float, float, float, float], width: int, height: int) -> tuple[int, int, int, int] | None:
    x0, y0 = max(math.floor(box[0]), 0), max(math.floor(box[1]), 0)
    x1, y1 = min(math.ceil(box[2]), width), min(math.ceil(box[3]), height)
    return (x0, y0, x1, y1) if x0 < x1 and y0 < y1 else None


def area(box: tuple[int, int, int, int]) -> int:
    return (box[2] - box[0]) * (box[3] - box[1])


def jumped(a: tuple[float, ...], b: tuple[float, ...], width: int, height: int) -> bool:
    limits = (JUMP * width, JUMP * height, JUMP * width, JUMP * height)
    return any(abs(p - q) > limit for p, q, limit in zip(a, b, limits, strict=True))


def pieces(sightings: list[tuple[int, tuple[float, float, float, float]]], width: int, height: int) -> list[list]:
    out = [[sightings[0]]]
    for seen in sightings[1:]:
        last = out[-1][-1]
        if seen[0] - last[0] > GAP or jumped(last[1], seen[1], width, height):
            out.append([])
        out[-1].append(seen)
    return out


def crop(done: Ingested, frame: int, box: tuple[int, int, int, int], track_id: str) -> str:
    rel = f"crops/{track_id}.png"
    out = done.frames[0].path.parent.parent / rel
    out.parent.mkdir(exist_ok=True)
    x0, y0, x1, y1 = box
    run("ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(done.frames[frame].path),
        "-vf", f"crop={x1 - x0}:{y1 - y0}:{x0}:{y0}", "-frames:v", "1", str(out))
    return rel


def find_regions(done: Ingested, sam: Sam, prompts: Sequence[str] = PROMPTS) -> tuple[list[Track], StageRun]:
    # a still goes as ingest's PNG, the frame its crops are cut from
    still = None if done.ad.media == "video" else done.frames[0].path.read_bytes()
    tracks = []

    def segment(prompt: str):
        return sam.segment(prompt, video=done.video) if still is None else sam.segment(prompt, image=still)

    with ThreadPoolExecutor(max_workers=len(prompts) or 1) as pool:
        results = list(pool.map(segment, prompts))
    for prompt, result in zip(prompts, results, strict=True):
        by_id: dict[int, list] = {}
        for frame in sorted(result.frames, key=lambda f: f.index):
            if frame.index >= len(done.frames):
                raise ValueError(f"sam returned frame {frame.index} but only {len(done.frames)} were sampled")
            for obj in frame.objects:
                by_id.setdefault(obj.id, []).append((frame.index, obj.box))
        for obj_id, sightings in by_id.items():
            for n, piece in enumerate(pieces(sightings, done.ad.width, done.ad.height)):
                track_id = f"{slug(prompt)}-{obj_id}" + (f"-{n}" if n else "")
                boxes = [(i, pixel_box(b, done.ad.width, done.ad.height)) for i, b in piece]
                boxes = [(i, b) for i, b in boxes if b]
                if not boxes:
                    continue
                largest = max(boxes, key=lambda s: (area(s[1]), -s[0]))[0]
                regions = tuple(
                    Region(
                        frame_time=done.frames[i].time,
                        box=b,
                        crop=crop(done, i, b, track_id) if i == largest else None,
                    )
                    for i, b in boxes
                )
                tracks.append(Track(track_id=track_id, prompt=prompt, regions=regions))
    tracks.sort(key=lambda t: (t.regions[0].frame_time, t.track_id))
    return tracks, StageRun(stage="regions", status="done", model=SAM, prompt=PROMPT_VERSION)
