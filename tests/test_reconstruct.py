import shutil
import subprocess
import types
from pathlib import Path

import pytest
from pydantic import ValidationError

from preflight.eval.reconstruct import FALLBACK_STILL, LABEL, AdDescription, Builder, Scene, ShotList, overlay_filter
from preflight.sources.rulings import Ruling, parse_ruling

FIXTURE = Path(__file__).parent / "fixtures" / "rulings"
FIXTURE = FIXTURE / "fixture-brightleaf-ltd-a26-1000001-fixture-brightleaf-ltd.html"


def ruling() -> Ruling:
    return parse_ruling(FIXTURE.read_text(encoding="utf-8"), f"https://www.asa.org.uk/rulings/{FIXTURE.name}")


# Leakage: the builder can see the ad description and nothing else from the ruling.


def test_ad_description_holds_only_id_and_description():
    assert set(AdDescription.model_fields) == {"ruling_id", "text"}
    desc = AdDescription.from_ruling(ruling())
    assert desc.text == ruling().ad_description
    dumped = desc.model_dump_json()
    for leaked in (ruling().assessment, ruling().issue, ruling().action, "upheld", "15.6.2"):
        assert leaked not in dumped


@pytest.mark.parametrize("field", ["assessment", "outcome", "issue", "cap_rules", "response"])
def test_ad_description_rejects_other_ruling_fields(field):
    with pytest.raises(ValidationError):
        AdDescription(ruling_id="A26-1000001", text="x", **{field: "anything"})


# A 1x1 PNG, so the fake client needs no fixture file.
ONE_PIXEL = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="


class Recorder:
    """Fake Meta client that records every request the builder makes."""

    def __init__(self):
        self.calls = []
        shots = ShotList(
            format="image",
            scenes=[
                Scene(
                    duration_seconds=4,
                    image_prompt="a bottle on a table",
                    on_screen_text=["Calms ADHD in kids"],
                    voiceover="",
                )
            ],
        )
        self.responses = types.SimpleNamespace(create=self._respond)
        self.images = types.SimpleNamespace(generate=self._image)
        self._shots = shots

    def _respond(self, **kwargs):
        self.calls.append(("responses", kwargs))
        return types.SimpleNamespace(output_text=self._shots.model_dump_json(), usage=None)

    def _image(self, **kwargs):
        self.calls.append(("images", kwargs))
        return types.SimpleNamespace(data=[types.SimpleNamespace(b64_json=ONE_PIXEL)])


def test_builder_refuses_a_ruling():
    with pytest.raises(TypeError):
        Builder(client=Recorder()).build(ruling())


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_requests_carry_no_assessment(tmp_path):
    client = Recorder()
    meta = Builder(client=client).build(AdDescription.from_ruling(ruling()), out_dir=tmp_path)
    sent = " ".join(str(value) for _, kwargs in client.calls for value in kwargs.values())
    r = ruling()
    assert r.ad_description in sent
    for leaked in (r.assessment, r.issue, r.action):
        assert leaked not in sent
    assert meta["reconstruction"] is True and meta["ruling_id"] == "A26-1000001"
    assert meta["label"] == LABEL
    assert (tmp_path / "A26-1000001" / "reconstruction.png").exists()


def test_spark_model_is_standard_mode():
    from preflight.eval import reconstruct

    assert "contributor" not in reconstruct.SHOTLIST_MODEL


def test_label_always_drawn():
    assert LABEL in overlay_filter([]).replace("\\", "")
    assert "Calms ADHD in kids" in overlay_filter(["Calms ADHD in kids"])


def test_long_text_is_shrunk_not_cut():
    lines = [f"Claim number {i} that the ad made in full" for i in range(20)]
    drawn = overlay_filter(lines)
    assert all(line in drawn for line in lines)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_a_line_with_a_percent_sign_is_drawn():
    drawn = subprocess.run(
        ["ffmpeg", "-v", "warning", "-f", "lavfi", "-i", "color=black:s=1080x1080", "-frames:v", "1",
         "-vf", overlay_filter(["Save 20% on your first order: 100% vegan"]), "-f", "null", "-"],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    # drawtext drops a line whose % it cannot expand, warning "Stray %"
    assert "%" not in drawn.stderr


class Refuser(Recorder):
    """Refuses the first image prompt the way the Meta API does."""

    def _image(self, **kwargs):
        if not any(kind == "images" for kind, _ in self.calls):
            self.calls.append(("images", kwargs))
            raise ValueError("Error code: 400 - the prompt triggered our content management policy.")
        return super()._image(**kwargs)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_refused_picture_falls_back_and_keeps_wording(tmp_path):
    client = Refuser()
    meta = Builder(client=client).build(AdDescription.from_ruling(ruling()), out_dir=tmp_path)
    prompts = [kwargs["prompt"] for kind, kwargs in client.calls if kind == "images"]
    assert len(prompts) == 2 and FALLBACK_STILL in prompts[1]
    assert meta["fallback_stills"] == [0]
    assert (tmp_path / "A26-1000001" / "reconstruction.png").exists()


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_redraw_renders_the_saved_scenes_without_a_model_call(tmp_path):
    Builder(client=Recorder()).build(AdDescription.from_ruling(ruling()), out_dir=tmp_path)
    picture = tmp_path / "A26-1000001" / "reconstruction.png"
    picture.unlink()
    client = Recorder()
    meta = Builder(client=client).redraw("A26-1000001", out_dir=tmp_path)
    assert client.calls == []
    assert picture.exists() and "redrawn_at" in meta
