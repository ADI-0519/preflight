from preflight.evidence.regions import area
from preflight.ingest import Ingested
from preflight.models import Spark
from preflight.schema import OnScreenText, StageRun, Track

PROMPT_VERSION = "on-screen-2"
EFFORT = "medium"
NUMBER = {"type": "number"}
SCHEMA = {
    "type": "object",
    "properties": {
        "texts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"}, "start": NUMBER, "end": NUMBER,
                    "x0": NUMBER, "y0": NUMBER, "x1": NUMBER, "y1": NUMBER,
                },
                "required": ["text", "start", "end", "x0", "y0", "x1", "y1"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["texts"],
    "additionalProperties": False,
}
PROMPT = "\n".join([
    "Transcribe verbatim every piece of text visible on screen, "
    "including small print, footnotes and text on packaging.",
    "Give one entry per continuous appearance of a piece of text.",
    "Give start and end in seconds from the start of the video.",
    "Ignore spoken words.",
    "For a still image use 0 for both start and end.",
    "Give the text's bounding box as x0, y0, x1, y1, each from 0 to 1000 as a share of the frame's width (x) "
    "or height (y), with 0, 0 the top-left corner.",
])
# boxes from Spark were up to 6% of the frame off in trials, so each edge is widened by this share
PAD = 0.05


def spark_box(item: dict, width: int, height: int) -> tuple[int, int, int, int] | None:
    x0 = max(round((item["x0"] / 1000 - PAD) * width), 0)
    y0 = max(round((item["y0"] / 1000 - PAD) * height), 0)
    x1 = min(round((item["x1"] / 1000 + PAD) * width), width)
    y1 = min(round((item["y1"] / 1000 + PAD) * height), height)
    # a box Spark gave back to front or empty would still have width from the padding
    if item["x1"] <= item["x0"] or item["y1"] <= item["y0"] or x0 >= x1 or y0 >= y1:
        return None
    return x0, y0, x1, y1


def read_on_screen(done: Ingested, spark: Spark) -> tuple[list[OnScreenText], StageRun]:
    if done.ad.media == "video":
        r = spark.ask(PROMPT, prompt_version=PROMPT_VERSION, effort=EFFORT, schema=SCHEMA, video=done.source)
    else:
        # ingest's PNG of the still, so the declared type is always right
        image = done.frames[0].path.read_bytes()
        r = spark.ask(PROMPT, prompt_version=PROMPT_VERSION, effort=EFFORT, schema=SCHEMA, image=image)
    duration = done.ad.duration or 0.0
    spans = []
    for item in r.data["texts"]:
        text = item["text"].strip()
        if not text:
            continue
        start = min(max(item["start"], 0.0), duration)
        end = min(max(item["end"], 0.0), duration)
        spans.append((start, text, max(end, start), spark_box(item, done.ad.width, done.ad.height)))
    spans.sort(key=lambda s: (s[0], s[1]))
    texts = [
        OnScreenText(text_id=f"text-{n}", text=text, start=start, end=end, box=box)
        for n, (start, text, end, box) in enumerate(spans)
    ]
    return texts, StageRun(stage="on_screen", status="done", model=r.model, prompt=PROMPT_VERSION, effort=EFFORT)


def overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> int:
    return max(min(a[2], b[2]) - max(a[0], b[0]), 0) * max(min(a[3], b[3]) - max(a[1], b[1]), 0)


def snap(texts: list[OnScreenText], tracks: list[Track]) -> list[OnScreenText]:
    out = []
    for text in texts:
        if text.box is None:
            out.append(text)
            continue
        middle = (text.start + text.end) / 2
        candidates = []
        for track in tracks:
            region = min(track.regions, key=lambda r: abs(r.frame_time - middle))
            # a label or bottle is larger than the padded box around one line of text, so only caption boxes fit
            if text.start <= region.frame_time <= text.end and area(region.box) <= area(text.box):
                candidates.append(region.box)
        best = max(candidates, key=lambda b: overlap(b, text.box), default=None)
        out.append(text.model_copy(update={"box": best}) if best and overlap(best, text.box) else text)
    return out
