import base64
import json
import shutil
import socket
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from preflight.eval import stress
from preflight.eval.reconstruct import LABEL, Builder, Scene, ShotList, overlay_filter
from preflight.eval.stress import (
    Skip,
    card,
    holds,
    music_bed,
    music_gain,
    render,
    small_overlay,
    small_text,
    speech_only,
    split_cuts,
)
from preflight.ingest import CARD_SECONDS, ingest_cards

CLAIMS = ["calms anxiety in children", "clinically proven to work"]
ONE_PIXEL = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="


def shots(fmt="video") -> ShotList:
    return ShotList(format=fmt, scenes=[
        Scene(duration_seconds=4, image_prompt="a bottle", voiceover="Meet our drops.",
              on_screen_text=["Calms anxiety in children", "Natural orange flavour"]),
        Scene(duration_seconds=3, image_prompt="a family", voiceover="",
              on_screen_text=["Clinically proven to work", "Order today"]),
    ])  # fmt: skip


def test_speech_only_moves_exactly_the_claim_lines():
    out = speech_only(shots(), CLAIMS)
    assert [s.on_screen_text for s in out.scenes] == [["Natural orange flavour"], ["Order today"]]
    spoken = ["Meet our drops. Calms anxiety in children", "Clinically proven to work"]
    assert [s.voiceover for s in out.scenes] == spoken


@pytest.mark.parametrize(("fmt", "claims"), [("image", CLAIMS), ("video", ["cures colds"])])
def test_speech_only_skips_a_still_or_an_ad_with_no_on_screen_claim(fmt, claims):
    with pytest.raises(Skip):
        speech_only(shots(fmt), claims)


def test_split_cuts_leaves_no_scene_holding_a_whole_claim():
    out, stills, whole = split_cuts(shots(), CLAIMS)
    assert whole == [] and stills == [0, 0, 1, 1]
    assert not any(holds(" ".join(s.on_screen_text), c) for s in out.scenes for c in CLAIMS)
    # the halves follow each other, and the words not in a claim stay where they were
    assert " ".join(out.scenes[0].on_screen_text + out.scenes[1].on_screen_text).split() == (
        "Calms anxiety Natural orange flavour in children".split()
    )
    assert out.scenes[1].voiceover == "" and out.scenes[0].duration_seconds == 2


def test_a_one_word_claim_cannot_be_split_and_is_skipped():
    one = ShotList(format="image", scenes=[Scene(duration_seconds=3, image_prompt="x", voiceover="",
                                                 on_screen_text=["Detox"])])  # fmt: skip
    with pytest.raises(Skip):
        split_cuts(one, ["detox"])


def test_small_text_shows_each_line_for_a_second_without_a_box():
    out = small_text(shots())
    assert [s.duration_seconds for s in out.scenes] == [4, 3]
    vf = small_overlay(out.scenes[0], "video")
    assert "between(t,0.0,1.0)" in vf and "between(t,1.0,2.0)" in vf and "fontsize=14" in vf
    # the only box is the label's
    assert vf.count("box=1") == 1


def test_a_small_still_shows_every_line_at_once():
    vf = small_overlay(shots("image").scenes[0], "image")
    assert "enable" not in vf and "Calms anxiety in children" in vf


def test_the_label_stays_in_every_drawn_variant():
    drawn = [
        small_overlay(shots().scenes[0], "video"),
        small_overlay(shots("image").scenes[0], "image"),
        *(overlay_filter(s.on_screen_text) for s in speech_only(shots(), CLAIMS).scenes),
        *(overlay_filter(s.on_screen_text) for s in split_cuts(shots(), CLAIMS)[0].scenes),
    ]
    assert all(LABEL in vf.replace("\\", "") for vf in drawn)


def test_music_sits_twelve_db_under_the_speech():
    assert music_gain(-20.0, -10.0) == -22.0
    assert "aevalsrc" in music_bed(5)


@pytest.mark.parametrize("kind", ["music", "speech_only"])
def test_a_kind_that_needs_a_soundtrack_skips_a_still(tmp_path, kind):
    (tmp_path / "shotlist.json").write_text(shots("image").model_dump_json(), encoding="utf-8")
    with pytest.raises(Skip):
        render(kind, tmp_path, tmp_path / "out", CLAIMS, Builder(client=False))


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
@pytest.mark.parametrize("kind", ["small_text", "split_cuts", "compressed", stress.ORDERED])
def test_still_variants_render(tmp_path, kind):
    source = tmp_path / "plain"
    source.mkdir()
    still = shots("image")
    (source / "shotlist.json").write_text(still.model_dump_json(), encoding="utf-8")
    for i in range(len(still.scenes)):
        (source / f"scene{i}.png").write_bytes(base64.b64decode(ONE_PIXEL))
    builder = Builder(client=False)
    builder.assemble(still, source)
    made = render(kind, source, tmp_path / "out", CLAIMS, builder)
    assert made and all(p.exists() for p in made)
    assert len(made) == (4 if kind in {"split_cuts", stress.ORDERED} else 2)
    if kind == stress.ORDERED:
        manifest = json.loads((tmp_path / "out" / "render.json").read_text())
        assert list(manifest["media"]) == [p.name for p in made]
        assert manifest["source_scene_indices"] == [0, 0, 1, 1]
        ingested = ingest_cards(made, tmp_path / "ingest")
        assert ingested.ad.media == "video" and ingested.audio is None
        assert ingested.ad.duration == pytest.approx(4 * CARD_SECONDS, abs=0.1)


def test_a_line_carrying_several_claims_has_each_claim_cut():
    line = "Reduces bloating in days; eliminates hot flashes fast; induces deep sleep tonight"
    claims = ["reduces bloating in days", "eliminates hot flashes fast", "induces deep sleep tonight"]
    many = ShotList(format="image", scenes=[Scene(duration_seconds=4, image_prompt="x", voiceover="",
                                                  on_screen_text=[line])])  # fmt: skip
    out, _, whole = split_cuts(many, claims)
    assert whole == [] and len(out.scenes) == 2
    assert sorted(" ".join(t for s in out.scenes for t in s.on_screen_text).split()) == sorted(line.split())


def test_cards_are_read_in_scene_order():
    names = ["reconstruction-10.png", "reconstruction-1.png", "reconstruction.png", "reconstruction-2.png"]
    assert [p.name for p in sorted(map(Path, names), key=card)] == [
        "reconstruction.png", "reconstruction-1.png", "reconstruction-2.png", "reconstruction-10.png"]


def test_ordered_variant_keeps_a_multi_claim_caption_in_reading_order():
    line = "Reduces bloating in days; eliminates hot flashes fast; induces deep sleep tonight"
    claims = ["reduces bloating in days", "eliminates hot flashes fast", "induces deep sleep tonight"]
    original = ShotList(format="image", scenes=[Scene(
        duration_seconds=4, image_prompt="a bottle", voiceover="", on_screen_text=[line],
    )])
    out, order, whole = stress.ordered_cuts(original, claims)
    pieces = [t for scene in out.scenes for t in scene.on_screen_text]
    assert " ".join(pieces).split() == line.split()
    assert len(out.scenes) == 4 and order == [0] * 4
    assert whole == []
    assert not any(holds(piece, claim) for piece in pieces for claim in claims)
    assert original.scenes[0].on_screen_text == [line]
    # Historical split_cuts is deliberately unchanged; it alternates disjoint pieces.
    assert stress.split_line(line, claims) == (
        "Reduces bloating flashes fast; induces deep", "in days; eliminates hot sleep tonight",
    )


class RecordingBuilder(Builder):
    def __init__(self):
        super().__init__(client=False)
        self.calls = 0

    def assemble(self, shots, target, stills=None, overlay=None):
        self.calls += 1
        for i, _ in enumerate(shots.scenes):
            stem = f"reconstruction-{i}" if i else "reconstruction"
            (target / f"{stem}.png").write_bytes(base64.b64decode(ONE_PIXEL))


@pytest.fixture
def ordered_source(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "shotlist.json").write_text(shots("image").model_dump_json(), encoding="utf-8")
    for i in range(2):
        (source / f"scene{i}.png").write_bytes(base64.b64decode(ONE_PIXEL))
    return source


def test_ordered_cache_reuses_only_verified_inputs_and_outputs(ordered_source, tmp_path):
    builder = RecordingBuilder()
    out = tmp_path / "out"
    made = render(stress.ORDERED, ordered_source, out, CLAIMS, builder)
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    assert render(stress.ORDERED, ordered_source, out, CLAIMS, builder) == made
    assert builder.calls == 1
    assert before == {p.name: p.read_bytes() for p in out.iterdir()}


@pytest.mark.parametrize("case", ["source", "claims", "media", "manifest", "shotlist", "extra-card"])
def test_ordered_cache_rejects_stale_or_partial_renders(ordered_source, tmp_path, case):
    out = tmp_path / "out"
    builder = RecordingBuilder()
    made = render(stress.ORDERED, ordered_source, out, CLAIMS, builder)
    claims = CLAIMS
    if case == "source":
        (ordered_source / "scene0.png").write_bytes(b"changed")
    elif case == "claims":
        claims = ["different claim"]
    elif case == "media":
        made[0].write_bytes(b"changed")
    elif case == "manifest":
        (out / "render.json").unlink()
    elif case == "shotlist":
        (out / "shotlist.json").write_text("{}")
    else:
        (out / "reconstruction-99.png").write_bytes(b"extra")
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    with pytest.raises(ValueError, match="incomplete or stale"):
        render(stress.ORDERED, ordered_source, out, claims, builder)
    assert builder.calls == 1
    assert before == {p.name: p.read_bytes() for p in out.iterdir()}


def test_ordered_one_word_ad_skips_without_creating_an_output_directory(ordered_source, tmp_path):
    out = tmp_path / "out"
    with pytest.raises(Skip):
        render(stress.ORDERED, ordered_source, out, ["flavour"], RecordingBuilder())
    assert not out.exists()


def test_ordered_lines_keep_their_own_sequence_and_voiceover_is_not_duplicated():
    original = shots()
    original.scenes[0].on_screen_text = ["Calms anxiety in children", "Clinically proven to work", "Orange flavour"]
    out, order, _ = stress.ordered_cuts(original, CLAIMS)
    assert out.scenes[0].on_screen_text == ["Calms anxiety", "Clinically proven", "Orange flavour"]
    assert out.scenes[1].on_screen_text == ["in children", "to work"]
    assert [s.voiceover for s in out.scenes] == ["Meet our drops.", "", "", ""]
    assert sum(s.duration_seconds for s in out.scenes) == 8
    assert order == [0, 0, 1, 1]


def test_render_only_cli_uses_dev_only_and_needs_no_provider_or_baseline(ordered_source, tmp_path, monkeypatch):
    from test_eval import truth

    monkeypatch.setattr(stress, "load_split", lambda _: SimpleNamespace(dev=["A24-000001"], test=["held-out"]))
    def labels(split, item):
        assert (split, item) == ("v2", "A24-000001")
        return truth(item, [(c, ["15.6.2"]) for c in CLAIMS])
    monkeypatch.setattr(stress, "load_ground_truth", labels)
    monkeypatch.setattr(stress, "OUT_DIR", tmp_path / "plain")
    (tmp_path / "plain").mkdir()
    ordered_source.rename(tmp_path / "plain" / "A24-000001")
    monkeypatch.setattr(stress, "Builder", lambda **kwargs: RecordingBuilder())
    monkeypatch.setattr(stress, "ensure_voice", lambda: pytest.fail("still render tried to download a voice"))
    monkeypatch.setattr(stress, "from_env", lambda: pytest.fail("render-only created provider clients"))
    monkeypatch.setattr(socket.socket, "connect", lambda *args: pytest.fail("render-only used the network"))
    monkeypatch.setattr(sys, "argv", [
        "stress", stress.ORDERED, "--render-only", "--render-root", str(tmp_path / "renders"),
    ])
    stress.main()
    manifest = tmp_path / "renders" / stress.ORDERED / "A24-000001" / "render.json"
    assert manifest.exists()
    assert not (tmp_path / "renders" / "split_cuts").exists()


def test_stress_screening_requires_a_baseline_before_any_labels_or_clients(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["stress", stress.ORDERED])
    monkeypatch.setattr(stress, "load_split", lambda *args: pytest.fail("missing baseline reached labels"))
    with pytest.raises(SystemExit, match="2"):
        stress.main()


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_ordered_silent_video_renders_and_ingests_all_scenes(ordered_source, tmp_path):
    silent = shots()
    for scene in silent.scenes:
        scene.voiceover = ""
    (ordered_source / "shotlist.json").write_text(silent.model_dump_json(), encoding="utf-8")
    out = tmp_path / "out"
    made = render(stress.ORDERED, ordered_source, out, CLAIMS, Builder(client=False))
    manifest = json.loads((out / "render.json").read_text())
    assert len(made) == 1 and made[0].suffix == ".mp4"
    assert manifest["rendered_seconds"] == pytest.approx(8, abs=0.1)
    done = ingest_cards(made, tmp_path / "ingest")
    assert done.ad.media == "video" and done.ad.duration == pytest.approx(8, abs=0.1)
    # Caption changes need not be shot cuts. All sampled frames, not just keyframes,
    # must remain available to the visual extraction stage.
    assert len(done.frames) == 16
    assert done.frames[-1].time == 7.5
