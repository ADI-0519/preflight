from preflight.ingest import Ingested
from preflight.models import Spark
from preflight.schema import OnScreenText, StageRun

PROMPT_VERSION = "on-screen-1"
EFFORT = "medium"
SCHEMA = {
    "type": "object",
    "properties": {
        "texts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"text": {"type": "string"}, "start": {"type": "number"}, "end": {"type": "number"}},
                "required": ["text", "start", "end"],
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
])


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
        spans.append((start, text, max(end, start)))
    spans.sort(key=lambda s: (s[0], s[1]))
    texts = [
        OnScreenText(text_id=f"text-{n}", text=text, start=start, end=end) for n, (start, text, end) in enumerate(spans)
    ]
    return texts, StageRun(stage="on_screen", status="done", model=r.model, prompt=PROMPT_VERSION, effort=EFFORT)
