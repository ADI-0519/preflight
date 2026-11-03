import base64
import shutil
from pathlib import Path

import pytest

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
@pytest.mark.parametrize("kind", ["small_text", "split_cuts", "compressed"])
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
    assert len(made) == (4 if kind == "split_cuts" else 2)


def test_a_line_carrying_several_claims_has_each_claim_cut():
    line = "Reduces bloating in days; eliminates hot flashes fast; induces deep sleep tonight"
    claims = ["reduces bloating in days", "eliminates hot flashes fast", "induces deep sleep tonight"]
    many = ShotList(format="image", scenes=[Scene(duration_seconds=4, image_prompt="x", voiceover="",
                                                  on_screen_text=[line])])  # fmt: skip
    out, stills, whole = split_cuts(many, claims)
    assert whole == [] and len(out.scenes) == 4 and stills == [0, 0, 0, 0]
    # the pieces follow each other in reading order, so every claim's halves sit on neighbouring scenes, in order
    assert " ".join(t for s in out.scenes for t in s.on_screen_text) == line
    assert [s.duration_seconds for s in out.scenes] == [1, 1, 1, 1]


def test_cards_are_read_in_scene_order():
    names = ["reconstruction-10.png", "reconstruction-1.png", "reconstruction.png", "reconstruction-2.png"]
    assert [p.name for p in sorted(map(Path, names), key=card)] == [
        "reconstruction.png", "reconstruction-1.png", "reconstruction-2.png", "reconstruction-10.png"]
