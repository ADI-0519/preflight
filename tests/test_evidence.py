import socket
from pathlib import Path

import pytest

from preflight.evidence.on_screen import PROMPT_VERSION as ON_SCREEN_PROMPT
from preflight.evidence.on_screen import read_on_screen, snap, spark_box
from preflight.evidence.regions import PROMPTS, find_regions
from preflight.ingest import Frame, Ingested, png_size, run
from preflight.models import SamFrame, SamObject, SamResult, SparkResult, Store, from_env
from preflight.models.store import digest
from preflight.schema import Ad, OnScreenText, Region, Track

FIXTURES = Path(__file__).parent / "fixtures" / "models"
CLIP = FIXTURES / "media" / "captions.mp4"
# the boxes drawn by scripts/record_model_fixtures.py, with the seconds each is on screen
CAPTIONS = [
    ("supports your immune system", (30, 52, 289, 84), 1.0, 4.0),
    ("clinically proven formula", (53, 52, 265, 84), 4.0, 7.0),
]
FOOTNOTE = "*vitamin d contributes"
# the footnote's pixels in the first frame
FOOTNOTE_BOX = (6, 165, 245, 174)


def ffmpeg(*args: str) -> None:
    run("ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", *args)


def hand_built(work: Path, media: str, count: int) -> Ingested:
    (work / "frames").mkdir()
    video = media == "video"
    ad = Ad(
        content_hash=digest(CLIP), media=media, width=320, height=180,
        duration=count / 2 if video else None, fps=2.0 if video else None,
    )
    frames = tuple(
        Frame(index=i, time=i / 2 if video else 0.0, path=work / "frames" / f"{i + 1:06d}.png") for i in range(count)
    )
    return Ingested(
        ad=ad, source=CLIP if video else work / "ad.png", audio=None, video=CLIP if video else None,
        rate=2.0 if video else None, threshold=0.3, frames=frames, keyframes=(0,),
    )


@pytest.fixture
def models(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network used in a replay test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setenv("META_API_KEY", "dummy")
    return from_env(Store(FIXTURES, "replay"))


@pytest.fixture
def captions(tmp_path):
    done = hand_built(tmp_path, "video", 16)
    ffmpeg("-i", str(CLIP), "-fps_mode", "passthrough", str(tmp_path / "frames" / "%06d.png"))
    return done


@pytest.fixture
def gray(tmp_path):
    done = hand_built(tmp_path, "video", 8)
    ffmpeg("-f", "lavfi", "-i", "color=c=gray:s=320x180:r=2:d=4", str(tmp_path / "frames" / "%06d.png"))
    return done


@pytest.fixture
def image(tmp_path):
    done = hand_built(tmp_path, "image", 1)
    done.source.write_bytes(b"jpeg")
    ffmpeg("-f", "lavfi", "-i", "color=c=gray:s=320x180", "-frames:v", "1", str(done.frames[0].path))
    return done


def near(a, b):
    return all(abs(p - q) <= 3 for p, q in zip(a, b, strict=True))


def test_caption_tracks_match_timings(captions, models):
    tracks, stage = find_regions(captions, models.sam)
    assert (stage.stage, stage.status, stage.model) == ("regions", "done", "sam-3.1")
    for _, box, start, end in CAPTIONS:
        (track,) = [t for t in tracks if t.prompt == "dark rectangle" and near(t.regions[0].box, box)]
        times = [r.frame_time for r in track.regions]
        assert abs(min(times) - start) <= 0.5
        assert abs(max(times) - end) <= 0.5


def test_on_screen_text_matches_timings(captions, models):
    texts, stage = read_on_screen(captions, models.spark)
    assert (stage.stage, stage.status, stage.prompt, stage.effort) == ("on_screen", "done", ON_SCREEN_PROMPT, "medium")
    for caption, _, start, end in CAPTIONS:
        (found,) = [t for t in texts if caption in t.text.lower()]
        assert abs(found.start - start) <= 1.0
        assert abs(found.end - end) <= 1.0
    (footnote,) = [t for t in texts if FOOTNOTE in t.text.lower()]
    assert contains(footnote.box, FOOTNOTE_BOX)


def contains(outer, inner):
    return outer[0] <= inner[0] and outer[1] <= inner[1] and outer[2] >= inner[2] and outer[3] >= inner[3]


def test_captions_snap_to_their_sam_boxes(captions, models):
    texts, _ = read_on_screen(captions, models.spark)
    tracks, _ = find_regions(captions, models.sam)
    placed = {t.text.lower(): t.box for t in snap(texts, tracks)}
    for caption, box, _, _ in CAPTIONS:
        assert placed[caption] == box
    # nothing sits behind the footnote, so it keeps Spark's padded box
    assert placed[FOOTNOTE + " to the normal function of the immune system"] == texts[0].box


def test_one_spark_call_per_ad(captions, models, monkeypatch):
    calls = []
    ask = type(models.spark).ask

    def counted(self, *args, **kwargs):
        calls.append(1)
        return ask(self, *args, **kwargs)

    monkeypatch.setattr(type(models.spark), "ask", counted)
    read_on_screen(captions, models.spark)
    assert len(calls) == 1


def test_crop_written(captions, models, tmp_path):
    tracks, _ = find_regions(captions, models.sam)
    assert tracks
    for track in tracks:
        (region,) = [r for r in track.regions if r.crop]
        x0, y0, x1, y1 = region.box
        assert png_size(tmp_path / region.crop) == (x1 - x0, y1 - y0)


class FakeSam:
    def __init__(self, frames):
        self.frames, self.calls = frames, []

    def segment(self, prompt, *, image=None, video=None):
        self.calls.append((prompt, image, video))
        return SamResult(self.frames, {})


def sam_frame(index, *boxes):
    return SamFrame(index, [SamObject(i, b, 0.9, "") for i, b in enumerate(boxes)])


def regions_of(tracks):
    return {t.track_id: [(r.frame_time, r.box) for r in t.regions] for t in tracks}


def test_boxes_are_rounded_outward_and_clamped(gray):
    sam = FakeSam([sam_frame(0, (10.2, 5.7, 100.1, 50.0), (-3.0, 170.5, 330.0, 190.0))])
    tracks, _ = find_regions(gray, sam, ["label"])
    assert regions_of(tracks) == {"label-0": [(0.0, (10, 5, 101, 50))], "label-1": [(0.0, (0, 170, 320, 180))]}


def test_degenerate_boxes_are_skipped(gray):
    sam = FakeSam([sam_frame(0, (320.0, 10.0, 330.0, 20.0), (5.0, 5.0, 40.0, 40.0))])
    tracks, _ = find_regions(gray, sam, ["label"])
    assert regions_of(tracks) == {"label-1": [(0.0, (5, 5, 40, 40))]}


def test_id_splits_on_a_gap_of_two_frames_only(gray):
    box = (5.0, 5.0, 40.0, 40.0)
    tracks, _ = find_regions(gray, FakeSam([sam_frame(i, box) for i in (0, 2)]), ["a b"])
    assert list(regions_of(tracks)) == ["a-b-0"]
    tracks, _ = find_regions(gray, FakeSam([sam_frame(i, box) for i in (0, 3, 4)]), ["a b"])
    assert regions_of(tracks) == {
        "a-b-0": [(0.0, (5, 5, 40, 40))],
        "a-b-0-1": [(1.5, (5, 5, 40, 40)), (2.0, (5, 5, 40, 40))],
    }


def test_box_jump_splits_a_track_but_jitter_does_not(gray):
    frames = [
        sam_frame(0, (30.0, 50.0, 290.0, 80.0)),
        sam_frame(1, (31.0, 51.0, 292.0, 80.0)),
        sam_frame(2, (53.0, 50.0, 265.0, 80.0)),
        sam_frame(3, (53.0, 50.0, 266.0, 80.0)),
    ]
    tracks, _ = find_regions(gray, FakeSam(frames), ["label"])
    times = {k: [t for t, _ in v] for k, v in regions_of(tracks).items()}
    assert times == {"label-0": [0.0, 0.5], "label-0-1": [1.0, 1.5]}
    frames = [sam_frame(0, (30.0, 50.0, 290.0, 80.0)), sam_frame(1, (30.0, 50.0, 300.0, 86.0))]
    tracks, _ = find_regions(gray, FakeSam(frames), ["label"])
    assert list(regions_of(tracks)) == ["label-0"]


def test_largest_region_gets_the_crop(gray):
    frames = [sam_frame(0, (0.0, 0.0, 10.0, 10.0)), sam_frame(1, (0.0, 0.0, 14.0, 14.0)),
              sam_frame(2, (0.0, 0.0, 14.0, 14.0))]
    (track,), _ = find_regions(gray, FakeSam(frames), ["label"])
    assert [r.crop for r in track.regions] == [None, "crops/label-0.png", None]


def test_frame_beyond_the_sampled_frames_raises(gray):
    with pytest.raises(ValueError, match="frame 8"):
        find_regions(gray, FakeSam([sam_frame(8, (0.0, 0.0, 10.0, 10.0))]), ["label"])


def test_sam_is_called_once_per_prompt_on_the_sampled_video(gray):
    sam = FakeSam([])
    tracks, _ = find_regions(gray, sam)
    assert tracks == []
    assert [c[0] for c in sam.calls] == list(PROMPTS)
    assert {c[2] for c in sam.calls} == {CLIP}


def test_still_image_has_frame_time_zero(image):
    sam = FakeSam([sam_frame(0, (5.0, 5.0, 40.0, 40.0))])
    (track,), _ = find_regions(image, sam, ["label"])
    assert track.regions[0].frame_time == 0.0
    assert sam.calls[0][1:] == (image.frames[0].path.read_bytes(), None)


class FakeSpark:
    def __init__(self, texts):
        self.texts, self.calls = texts, []

    def ask(self, text, **kwargs):
        self.calls.append(kwargs)
        return SparkResult("muse-spark-1.3", "", {"texts": self.texts}, {})


def item(text, start, end, box=(100, 100, 200, 200)):
    return {"text": text, "start": start, "end": end} | dict(zip(("x0", "y0", "x1", "y1"), box, strict=True))


def test_spark_box_is_scaled_padded_and_clamped():
    assert spark_box(item("a", 0, 0, (100, 500, 600, 550)), 1000, 200) == (50, 90, 650, 120)
    assert spark_box(item("a", 0, 0, (0, 0, 1000, 1000)), 320, 180) == (0, 0, 320, 180)
    assert spark_box(item("a", 0, 0, (600, 500, 100, 550)), 1000, 200) is None
    assert spark_box(item("a", 0, 0, (0, 0, 0, 0)), 1000, 200) is None


def text_at(box, start=1.0, end=3.0):
    return OnScreenText(text_id="text-0", text="a", start=start, end=end, box=box)


def track_at(box, times, prompt="dark rectangle"):
    return Track(track_id=f"t{box[0]}", prompt=prompt, regions=tuple(Region(frame_time=t, box=box) for t in times))


def test_snap_takes_a_caption_box_inside_the_padded_box():
    (text,) = snap([text_at((0, 40, 300, 100))], [track_at((20, 50, 280, 90), [1.5, 2.0, 2.5])])
    assert text.box == (20, 50, 280, 90)


def test_snap_ignores_larger_regions_other_times_and_unplaced_text():
    label = track_at((0, 0, 320, 180), [2.0], "label")
    later = track_at((20, 50, 280, 90), [5.0, 5.5])
    elsewhere = track_at((0, 150, 100, 170), [2.0])
    texts = [text_at((0, 40, 300, 100)), text_at(None)]
    assert snap(texts, [label, later, elsewhere]) == texts


def test_spark_output_is_clamped_sorted_and_numbered(gray):
    spark = FakeSpark([item("b", 2, 3), item("  ", 0, 1), item("a", 2, 1), item("late", 7, 20), item("early", -1, 1)])
    texts, stage = read_on_screen(gray, spark)
    assert [(t.text_id, t.text, t.start, t.end) for t in texts] == [
        ("text-0", "early", 0.0, 1.0),
        ("text-1", "a", 2.0, 2.0),
        ("text-2", "b", 2.0, 3.0),
        ("text-3", "late", 4.0, 4.0),
    ]
    assert all(t.box == (16, 9, 80, 45) for t in texts)
    assert stage.model == "muse-spark-1.3"
    assert spark.calls[0]["video"] == CLIP and "image" not in spark.calls[0]


def test_image_ad_sends_the_image(image):
    spark = FakeSpark([item("sale", 5, 9)])
    (text,), _ = read_on_screen(image, spark)
    assert (text.start, text.end) == (0.0, 0.0)
    assert spark.calls[0]["image"] == image.frames[0].path.read_bytes() and "video" not in spark.calls[0]


def test_model_errors_propagate(gray):
    class Failing:
        def ask(self, *args, **kwargs):
            raise RuntimeError("spark down")

        def segment(self, *args, **kwargs):
            raise RuntimeError("sam down")

    with pytest.raises(RuntimeError, match="spark down"):
        read_on_screen(gray, Failing())
    with pytest.raises(RuntimeError, match="sam down"):
        find_regions(gray, Failing())
