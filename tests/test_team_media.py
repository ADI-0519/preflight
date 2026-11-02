import sys
from pathlib import Path

import pytest

from preflight.eval import team_media
from preflight.eval.split import Split, TeamAd


@pytest.fixture
def split(monkeypatch, tmp_path):
    monkeypatch.setattr(team_media, "TEAM_DIR", tmp_path)
    split = Split(
        version="fixture", frozen=False, created="2026-11-02", dev=["A26-1000001", "T16", "T17"], test=["T26"]
    )
    monkeypatch.setattr(team_media, "load_split", lambda version: split)
    return split


def test_a_part_selects_only_its_own_team_items(split):
    assert team_media.selected_items(split, "dev", None) == ["T16", "T17"]
    assert team_media.selected_items(split, "test", None) == ["T26"]
    assert team_media.selected_items(split, None, ["T26", "T17"]) == ["T17", "T26"]


@pytest.mark.parametrize("only", [["T26"], ["A26-1000001"], ["T99"]])
def test_an_item_outside_the_part_is_refused(split, only):
    with pytest.raises(ValueError, match="not a team item"):
        team_media.selected_items(split, "dev", only)


def test_only_the_selected_copy_is_opened_and_an_image_needs_no_voice(split, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["team_media", "--part", "dev", "--only", "T17"])
    monkeypatch.setattr(team_media.shutil, "which", lambda name: name)
    opened = []

    def load(item_id):
        opened.append(item_id)
        return TeamAd(
            item_id=item_id, format="image", product="pack", register_ids=[], on_screen_text=["x"], voiceover=""
        )

    monkeypatch.setattr(team_media, "load_team_ad", load)
    monkeypatch.setattr(team_media, "ensure_voice", lambda: pytest.fail("an image ad downloaded the voice"))
    monkeypatch.setattr(team_media, "Builder", lambda **kwargs: None)
    monkeypatch.setattr(team_media, "build_team", lambda ad, builder: Path("ad.png"))
    team_media.main()
    assert opened == ["T17"]


def test_a_built_item_is_neither_opened_nor_rendered(split, monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["team_media", "--part", "dev", "--only", "T16"])
    (tmp_path / "T16").mkdir()
    (tmp_path / "T16" / "meta.json").write_text("{}")
    (tmp_path / "T16" / "ad.png").write_bytes(b"png")
    monkeypatch.setattr(team_media, "load_team_ad", lambda item_id: pytest.fail("a built item was opened"))
    monkeypatch.setattr(team_media, "Builder", lambda **kwargs: pytest.fail("a client was started"))
    team_media.main()


def test_metadata_without_a_render_is_not_built(split, tmp_path):
    (tmp_path / "T16").mkdir()
    (tmp_path / "T16" / "meta.json").write_text("{}")
    assert not team_media.built("T16")
