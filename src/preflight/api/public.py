"""Public mode for the live demo (P67): per-client limits, a daily spend cap and a switch that stops uploads.

The mode is read from PREFLIGHT_PUBLIC_MODE on every request, so changing it needs a restart, not a redeploy:
"on" applies the limits, "replay" also refuses uploads so that only the preloaded demos run, and anything else
(or unset) leaves the workspace as it runs locally, unless Settings.public turns the limits on.
"""

import json
import os
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Literal

from preflight.api.storage import APIError, Settings, write_json
from preflight.eval.reconstruct import IMAGE_EACH, SPARK_IN, SPARK_OUT
from preflight.eval.run import MeteredSam, MeteredTranscribe
from preflight.models.clients import Models

MODE_ENV = "PREFLIGHT_PUBLIC_MODE"
HOUR = 3600
UPLOAD_NOTICE = (
    "Your ad is sent to the Meta Model API in Standard mode, which does not use it for training. It is deleted "
    "after {hours:g} hours. Do not upload confidential ads."
)

Mode = Literal["off", "on", "replay"]


def mode(settings: Settings) -> Mode:
    value = os.environ.get(MODE_ENV, "").strip().lower()
    if value == "replay":
        return "replay"
    return "on" if value == "on" or settings.public else "off"


def spark_cost(usage: dict) -> float:
    return (usage.get("input_tokens", 0) * SPARK_IN + usage.get("output_tokens", 0) * SPARK_OUT) / 1e6


class _Spark:
    def __init__(self, client, usd: list[float]):
        self.client, self.usd = client, usd

    def ask(self, *args, **kwargs):
        r = self.client.ask(*args, **kwargs)
        self.usd.append(spark_cost(r.usage))
        return r

    def respond(self, *args, **kwargs):
        r = self.client.respond(*args, **kwargs)
        self.usd.append(spark_cost(r.usage))
        return r

    def __getattr__(self, name):
        return getattr(self.client, name)


class _Image:
    def __init__(self, client, usd: list[float]):
        self.client, self.usd = client, usd

    def generate(self, *args, **kwargs):
        self.usd.append(IMAGE_EACH)
        return self.client.generate(*args, **kwargs)

    def edit(self, *args, **kwargs):
        self.usd.append(IMAGE_EACH)
        return self.client.edit(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.client, name)


def metered(models: Models) -> tuple[Models, Callable[[], float]]:
    """The models with every call priced; a cached answer is priced as if called, so the count errs high."""
    usd: list[float] = []
    sam, heard = MeteredSam(models.sam), MeteredTranscribe(models.transcribe)
    spark, image = _Spark(models.spark, usd), _Image(models.image, usd) if models.image else None
    return Models(spark, heard, sam, image, models.glimmer), lambda: sum(usd) + sum(sam.usd) + sum(heard.usd)


class Public:
    def __init__(self, settings: Settings, clock: Callable[[], float] = time.time):
        self.settings, self.clock = settings, clock
        self.lock = threading.Lock()
        self.starts: dict[tuple[str, str], list[float]] = {}

    @property
    def mode(self) -> Mode:
        return mode(self.settings)

    def max_upload_bytes(self) -> int:
        s = self.settings
        return min(s.max_upload_bytes, s.public_max_upload_bytes) if self.mode != "off" else s.max_upload_bytes

    def max_seconds(self, default: float) -> float:
        return min(default, self.settings.public_max_seconds) if self.mode != "off" else default

    def _today(self) -> str:
        return datetime.fromtimestamp(self.clock(), UTC).date().isoformat()

    def _ledger(self) -> dict:
        path = self.settings.root / "spend.json"
        fields = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        return fields if fields.get("day") == self._today() else {"day": self._today(), "usd": 0.0}

    def spent(self) -> float:
        with self.lock:
            return self._ledger()["usd"]

    def spend(self, usd: float) -> None:
        # every job adds to the day's count, so the cap holds the moment public mode is switched on
        with self.lock:
            fields = self._ledger()
            self.settings.root.mkdir(parents=True, exist_ok=True)
            write_json(self.settings.root / "spend.json", fields | {"usd": round(fields["usd"] + usd, 6)})

    def closed(self) -> str | None:
        """Why new model work is refused, or None."""
        if self.mode == "replay":
            return "uploads_paused"
        if self.mode == "on" and self.spent() >= self.settings.daily_cap_usd:
            return "daily_cap_reached"
        return None

    @contextmanager
    def admit(self, client: str, kind: Literal["upload", "screening", "fix"]) -> Iterator[None]:
        if self.mode == "off":
            yield
            return
        if reason := self.closed():
            raise APIError(503, reason)
        s = self.settings
        allowed = {"upload": s.public_uploads_per_hour, "screening": s.public_screenings_per_hour,
                   "fix": s.public_fixes_per_hour}[kind]
        with self.lock:
            now = self.clock()
            recent = [t for t in self.starts.get((client, kind), []) if t > now - HOUR]
            if len(recent) >= allowed:
                raise APIError(429, "rate_limited")
            self.starts[(client, kind)] = [*recent, now]
        try:
            yield
        except APIError:
            # a refused start (unknown upload, full queue) does not use up the visitor's allowance
            with self.lock:
                self.starts[(client, kind)].remove(now)
            raise
