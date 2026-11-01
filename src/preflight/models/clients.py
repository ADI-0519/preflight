import base64
import json
import os
import re
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAI

from preflight.models.store import UPLOAD_TTL_SECONDS, Store, digest, encode_bytes, with_retry

BASE_URL = "https://api.meta.ai/v1"
GLIMMER_BASE_URL = "https://inference.baseten.co/v1"
SPARK = "muse-spark-1.3"
TRANSCRIBE = "muse-voice-transcribe-1.0"
SAM = "sam-3.1"
IMAGE = "muse-image-1.0"

_FRAME = re.compile(r"<(\d+)f>")
# objects on a frame line are joined by commas
_OBJECT = re.compile(r",?(\d+)<\|box;(.*?)\|><\|mask;(.*?)\|>(?=,\d+<\|box;|\s*$)", re.DOTALL)


@dataclass
class SparkResult:
    model: str
    text: str
    data: dict | None
    usage: dict
    # wall time of the original call; None for responses cached before it was recorded
    seconds: float | None = None


@dataclass
class SparkTurn:
    model: str
    output: list[dict]
    text: str
    usage: dict
    seconds: float | None = None

    @property
    def calls(self) -> list[dict]:
        return [item for item in self.output if item["type"] == "function_call"]


@dataclass
class Turn:
    start_ms: int
    end_ms: int
    text: str
    speaker: str | None


@dataclass
class SamObject:
    id: int
    box: tuple[float, float, float, float]
    confidence: float | None
    mask: str = field(repr=False)


@dataclass
class SamFrame:
    index: int
    objects: list[SamObject]


@dataclass
class SamResult:
    frames: list[SamFrame]
    usage: dict


@dataclass
class ChatResult:
    model: str
    text: str
    usage: dict


@contextmanager
def uploaded(api: OpenAI, path: Path):
    # rule 6: uploads expire within the hour and are deleted as soon as the call ends
    with path.open("rb") as f:
        file_id = api.files.create(
            file=f, purpose="user_data", expires_after={"anchor": "created_at", "seconds": UPLOAD_TTL_SECONDS}
        ).id
    try:
        yield file_id
    finally:
        api.files.delete(file_id)


def data_url(image: bytes, mime: str) -> str:
    return f"data:{mime};base64,{encode_bytes(image)}"


def usage_of(response) -> dict:
    return response.usage.model_dump() if response.usage else {}


@dataclass
class Spark:
    store: Store
    api: OpenAI = field(repr=False)
    sleep: Callable[[float], None] = time.sleep

    def ask(
        self,
        text: str,
        *,
        prompt_version: str,
        effort: str,
        schema: dict | None = None,
        image: bytes | None = None,
        image_mime: str = "image/png",
        video: Path | None = None,
    ) -> SparkResult:
        parts = {
            "kind": "spark", "text": text, "prompt_version": prompt_version, "effort": effort, "schema": schema,
            "image": image and digest(image), "image_mime": image and image_mime, "video": video and digest(video),
        }

        def respond(content: list[dict]) -> dict:
            kwargs = {}
            if schema is not None:
                kwargs["text"] = {"format": {"type": "json_schema", "name": "output", "schema": schema, "strict": True}}
            began = time.monotonic()
            r = self.api.responses.create(
                model=SPARK,
                input=[{"type": "message", "role": "user", "content": content}],
                reasoning={"effort": effort},
                **kwargs,
            )
            # a truncated or malformed answer must fail here, before the store caches it
            if r.status != "completed":
                raise RuntimeError(f"{SPARK} response {r.status}: {r.incomplete_details}")
            if schema is not None:
                json.loads(r.output_text)
            return {
                "model": r.model, "text": r.output_text, "usage": usage_of(r), "seconds": time.monotonic() - began,
            }

        def call() -> dict:
            content = [{"type": "input_text", "text": text}]
            if image is not None:
                content.append({"type": "input_image", "image_url": data_url(image, image_mime)})
            if video is None:
                return respond(content)
            with uploaded(self.api, video) as file_id:
                return respond([*content, {"type": "input_file", "file_id": file_id}])

        r = self.store.fetch(SPARK, parts, lambda: with_retry(call, self.sleep))
        data = json.loads(r["text"]) if schema is not None else None
        return SparkResult(r["model"], r["text"], data, r["usage"], r.get("seconds"))

    def respond(
        self, input: list[dict], *, tools: list[dict], prompt_version: str, effort: str,
        instructions: str | None = None,
    ) -> SparkTurn:
        parts = {
            "kind": "spark_tools", "input": input, "tools": tools, "prompt_version": prompt_version, "effort": effort,
            "instructions": instructions,
        }

        def call() -> dict:
            began = time.monotonic()
            r = self.api.responses.create(
                model=SPARK, input=input, tools=tools, reasoning={"effort": effort},
                **({"instructions": instructions} if instructions else {}),
            )
            if r.status != "completed":
                raise RuntimeError(f"{SPARK} response {r.status}: {r.incomplete_details}")
            return {
                "model": r.model, "output": [item.model_dump(exclude_none=True) for item in r.output],
                "text": r.output_text, "usage": usage_of(r), "seconds": time.monotonic() - began,
            }

        r = self.store.fetch(SPARK, parts, lambda: with_retry(call, self.sleep))
        return SparkTurn(r["model"], r["output"], r["text"], r["usage"], r.get("seconds"))


@dataclass
class VoiceTranscribe:
    store: Store
    key: str = field(repr=False)
    http: httpx.Client = field(default_factory=lambda: httpx.Client(timeout=120), repr=False)
    base_url: str = BASE_URL
    sleep: Callable[[float], None] = time.sleep

    def transcribe(self, wav: bytes) -> list[Turn]:
        if wav[:4] != b"RIFF" or wav[8:12] != b"WAVE":
            raise ValueError("audio must be WAV")
        request = {"mode": "DIARIZATION", "model": TRANSCRIBE, "audioEncoding": "WAV"}

        def call() -> dict:
            r = self.http.post(
                f"{self.base_url}/asr/transcribe",
                headers={"Authorization": f"Bearer {self.key}"},
                files={
                    "request": (None, json.dumps(request), "application/json"),
                    "audio": ("audio.wav", wav, "audio/wav"),
                },
            )
            r.raise_for_status()
            return r.json()

        parts = {"kind": "transcribe", "request": request, "audio": digest(wav)}
        r = self.store.fetch(TRANSCRIBE, parts, lambda: with_retry(call, self.sleep))
        return [Turn(t["startMs"], t["endMs"], t["transcript"], t.get("speaker")) for t in r["turns"]]


def parse_sam(text: str) -> list[SamFrame]:
    pieces = _FRAME.split(text)
    frames = []
    for index, body in zip(pieces[1::2], pieces[2::2], strict=True):
        matches = list(_OBJECT.finditer(body))
        # an object the pattern misses would read as nothing found, so fail instead
        if "".join(m[0] for m in matches) != body.strip():
            raise ValueError(f"unparsed {SAM} output in frame {index}")
        objects = []
        for m in matches:
            box = dict(field.split("=", 1) for field in m[2].split(";"))
            corners = (float(box["x1"]), float(box["y1"]), float(box["x2"]), float(box["y2"]))
            objects.append(SamObject(int(m[1]), corners, float(box["c"]) if "c" in box else None, m[3]))
        frames.append(SamFrame(int(index), objects))
    return frames


@dataclass
class Sam:
    store: Store
    api: OpenAI = field(repr=False)
    sleep: Callable[[float], None] = time.sleep

    def segment(
        self, prompt: str, *, image: bytes | None = None, image_mime: str = "image/png", video: Path | None = None
    ) -> SamResult:
        if (image is None) == (video is None):
            raise ValueError("give exactly one of image or video")
        parts = {
            "kind": "sam", "prompt": prompt, "image": image and digest(image), "image_mime": image and image_mime,
            "video": video and digest(video),
        }

        def stream(media: dict) -> dict:
            deltas = []
            with self.api.responses.stream(
                model=SAM,
                input=[{"type": "message", "role": "user", "content": [{"type": "input_text", "text": prompt}, media]}],
                metadata={"include_confidence": "true"},
            ) as events:
                for event in events:
                    if event.type == "response.output_text.delta":
                        deltas.append(event.delta)
                final = events.get_final_response()
            return {"model": final.model, "text": "".join(deltas), "usage": usage_of(final)}

        def call() -> dict:
            if image is not None:
                return stream({"type": "input_image", "image_url": data_url(image, image_mime)})
            with uploaded(self.api, video) as file_id:
                return stream({"type": "input_video", "file_id": file_id})

        r = self.store.fetch(SAM, parts, lambda: with_retry(call, self.sleep))
        return SamResult(parse_sam(r["text"]), r["usage"])


@dataclass
class Image:
    store: Store
    api: OpenAI = field(repr=False)
    sleep: Callable[[float], None] = time.sleep

    def generate(self, prompt: str) -> bytes:
        return self._png(
            {"kind": "image_generate", "prompt": prompt},
            lambda: self.api.images.generate(model=IMAGE, prompt=prompt, n=1, output_format="png"),
        )

    def edit(self, image: bytes, prompt: str) -> bytes:
        return self._png(
            {"kind": "image_edit", "prompt": prompt, "image": digest(image)},
            lambda: self.api.images.edit(
                model=IMAGE, prompt=prompt, image=("image.png", image, "image/png"), n=1, output_format="png"
            ),
        )

    def _png(self, parts: dict, request: Callable) -> bytes:
        def call() -> dict:
            return {"model": IMAGE, "png": request().data[0].b64_json}

        return base64.b64decode(self.store.fetch(IMAGE, parts, lambda: with_retry(call, self.sleep))["png"])


@dataclass
class Glimmer:
    store: Store
    model: str
    api: OpenAI = field(repr=False)
    sleep: Callable[[float], None] = time.sleep

    def ask(
        self, text: str, *, prompt_version: str, image: bytes | None = None, image_mime: str = "image/png"
    ) -> ChatResult:
        parts = {
            "kind": "glimmer", "text": text, "prompt_version": prompt_version,
            "image": image and digest(image), "image_mime": image and image_mime,
        }
        content = [{"type": "text", "text": text}]
        if image is not None:
            content.append({"type": "image_url", "image_url": {"url": data_url(image, image_mime)}})

        def call() -> dict:
            r = self.api.chat.completions.create(model=self.model, messages=[{"role": "user", "content": content}])
            return {"model": r.model, "text": r.choices[0].message.content, "usage": usage_of(r)}

        r = self.store.fetch(self.model, parts, lambda: with_retry(call, self.sleep))
        return ChatResult(r["model"], r["text"], r["usage"])


@dataclass
class Models:
    spark: Spark
    transcribe: VoiceTranscribe
    sam: Sam
    image: Image
    glimmer: Glimmer | None


def from_env(store: Store | None = None, sleep: Callable[[float], None] = time.sleep) -> Models:
    load_dotenv()
    store = store or Store()
    key = os.environ["META_API_KEY"]
    meta = OpenAI(base_url=BASE_URL, api_key=key, max_retries=0)
    glimmer = None
    if os.environ.get("GLIMMER_MODEL") and os.environ.get("BASETEN_API_KEY"):
        baseten = OpenAI(
            base_url=os.environ.get("GLIMMER_BASE_URL", GLIMMER_BASE_URL),
            api_key=os.environ["BASETEN_API_KEY"],
            max_retries=0,
        )
        glimmer = Glimmer(store, os.environ["GLIMMER_MODEL"], baseten, sleep)
    return Models(
        Spark(store, meta, sleep),
        VoiceTranscribe(store, key, sleep=sleep),
        Sam(store, meta, sleep),
        Image(store, meta, sleep),
        glimmer,
    )
