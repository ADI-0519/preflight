import base64
import hashlib
import json
import os
import time
from collections.abc import Callable
from pathlib import Path

import httpx
import openai

DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data" / "cache"
MAX_ATTEMPTS = 5
UPLOAD_TTL_SECONDS = 3600


class CacheMiss(RuntimeError):
    pass


def check_model(model: str) -> None:
    # rule 10: Standard mode only, never the training-enabled model
    if "contributor" in model.lower():
        raise ValueError(f"contributor-mode model refused: {model}")


def digest(data: bytes | Path) -> str:
    h = hashlib.sha256()
    if isinstance(data, Path):
        with data.open("rb") as f:
            while chunk := f.read(1 << 20):
                h.update(chunk)
    else:
        h.update(data)
    return h.hexdigest()


def encode_bytes(data: bytes) -> str:
    return base64.b64encode(data).decode()


class Store:
    def __init__(self, root: Path | str = DEFAULT_ROOT, mode: str = "cache"):
        if mode not in ("cache", "replay"):
            raise ValueError(f"unknown store mode: {mode}")
        self.root, self.mode = Path(root), mode

    def fetch(self, model: str, parts: dict, call: Callable[[], dict]) -> dict:
        check_model(model)
        key = hashlib.sha256(
            json.dumps({"model": model, **parts}, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        path = self.root / model.replace("/", "__") / f"{key}.json"
        if path.exists():
            response = json.loads(path.read_text(encoding="utf-8"))["response"]
            check_model(str(response.get("model", model)))
            return response
        if self.mode == "replay":
            raise CacheMiss(f"no recorded response for {model} key {key}")
        response = call()
        check_model(str(response.get("model", model)))
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        # rule 6: the request holds ad text, so only the key and the response are kept
        tmp.write_text(json.dumps({"key": key, "response": response}), encoding="utf-8")
        tmp.replace(path)
        return response


RETRY_STATUSES = {429, 500, 502, 503, 504}


def with_retry(call: Callable[[], dict], sleep: Callable[[float], None] = time.sleep) -> dict:
    for attempt in range(MAX_ATTEMPTS):
        headers = {}
        try:
            return call()
        except (openai.APIStatusError, httpx.HTTPStatusError) as e:
            if e.response.status_code not in RETRY_STATUSES or attempt == MAX_ATTEMPTS - 1:
                raise
            headers = e.response.headers
        except (openai.APIConnectionError, httpx.TransportError):
            if attempt == MAX_ATTEMPTS - 1:
                raise
        try:
            delay = float(headers["Retry-After"])
        except (KeyError, ValueError):
            delay = 2.0**attempt
        sleep(delay)
    raise AssertionError("unreachable")
