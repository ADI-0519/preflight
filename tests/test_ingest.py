import functools
import http.server
import json
import subprocess
import threading
import wave

import pytest

from preflight import ingest as ingest_module
from preflight.ingest import CARD_SECONDS, capture, ingest, ingest_cards, load
from preflight.models.store import digest


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def make_video(path, audio=True):
    # the fps filter rounds to the nearest slot, so the cut at 2.3 s lands in sampled frame 5
    red, blue = "color=c=red:s=320x180:r=25:d=2.3", "color=c=blue:s=320x180:r=25:d=2.7"
    inputs = ["-f", "lavfi", "-i", red, "-f", "lavfi", "-i", blue]
    graph = "[0:v][1:v]concat=n=2:v=1:a=0[v]"
    maps = ["-map", "[v]"]
    if audio:
        inputs += ["-f", "lavfi", "-i", "sine=frequency=440:duration=5"]
        maps += ["-map", "2:a"]
    ffmpeg(*inputs, "-filter_complex", graph, *maps, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path))
    return path


def make_image(path):
    ffmpeg("-f", "lavfi", "-i", "color=c=green:s=200x120", "-frames:v", "1", str(path))
    return path


def probe_video(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-print_format", "json",
         "-show_entries", "stream=codec_name,nb_read_frames", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)["streams"][0]


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    return make_video(tmp_path_factory.mktemp("media") / "ad.mp4")


def test_video_ingest(video, tmp_path):
    done = ingest(video, tmp_path / "work")
    assert (done.ad.media, done.ad.width, done.ad.height, done.ad.fps) == ("video", 320, 180, 25)
    assert done.ad.duration == pytest.approx(5, abs=0.1)
    assert done.ad.content_hash == digest(video)
    assert done.source == video.resolve()
    assert [f.time for f in done.frames] == [i / 2 for i in range(10)]
    assert all(f.path.exists() for f in done.frames)
    assert done.keyframes == (0, 5)
    with wave.open(str(done.audio)) as wav:
        assert (wav.getnchannels(), wav.getframerate(), wav.getsampwidth()) == (1, 16000, 2)
        assert wav.getnframes() / 16000 == pytest.approx(5, abs=0.1)
    assert probe_video(done.video) == {"codec_name": "h264", "nb_read_frames": "10"}
    assert not list((tmp_path / "work").glob(".tmp-*"))


def test_video_without_audio(tmp_path):
    done = ingest(make_video(tmp_path / "mute.mp4", audio=False), tmp_path / "work")
    assert done.audio is None
    assert len(done.frames) == 10
    assert done.keyframes == (0, 5)


@pytest.mark.parametrize("suffix", ["png", "jpg"])
def test_image_ingest(tmp_path, suffix):
    done = ingest(make_image(tmp_path / f"ad.{suffix}"), tmp_path / "work")
    assert (done.ad.media, done.ad.width, done.ad.height) == ("image", 200, 120)
    assert (done.ad.duration, done.ad.fps, done.audio, done.video, done.rate) == (None,) * 5
    assert [(f.index, f.time) for f in done.frames] == [(0, 0.0)]
    assert done.frames[0].path.exists()
    assert done.keyframes == (0,)


def test_cards_are_read_as_one_silent_slideshow_with_a_cut_at_each_card(tmp_path):
    red, blue = tmp_path / "card.png", tmp_path / "card-1.jpg"
    make_image(red)
    # a card of another size is fitted to the first card's frame
    ffmpeg("-f", "lavfi", "-i", "color=c=blue:s=100x100", "-frames:v", "1", str(blue))
    done = ingest_cards([red, blue], tmp_path / "work")
    assert (done.ad.media, done.ad.width, done.ad.height, done.audio) == ("video", 200, 120, None)
    assert done.ad.duration == pytest.approx(2 * CARD_SECONDS, abs=0.1)
    # ingest samples two frames a second, so the second card starts at frame 2 * CARD_SECONDS
    assert done.keyframes == (0, 2 * CARD_SECONDS)
    # the same cards in the same order reuse the slideshow, so the ingest is cached on the same bytes
    assert ingest_cards([red, blue], tmp_path / "work").ad.content_hash == done.ad.content_hash
    assert ingest_cards([blue, red], tmp_path / "work").ad.content_hash != done.ad.content_hash


def test_one_card_is_ingested_as_a_still(tmp_path):
    done = ingest_cards([make_image(tmp_path / "card.png")], tmp_path / "work")
    assert done.ad.media == "image" and not (tmp_path / "work" / "carousels").exists()


def test_page_screenshot(tmp_path):
    done = ingest(make_image(tmp_path / "page.png"), tmp_path / "work", media="page")
    assert done.ad.media == "page"


def test_rerun_reuses_output(video, tmp_path, monkeypatch):
    first = ingest(video, tmp_path / "work")

    real = subprocess.run

    def refuse_ffmpeg(cmd, *args, **kwargs):
        assert cmd[0] != "ffmpeg", "ffmpeg ran on a rerun"
        return real(cmd, *args, **kwargs)

    monkeypatch.setattr(ingest_module.subprocess, "run", refuse_ffmpeg)
    assert ingest(video, tmp_path / "work") == first


def test_rerun_points_at_the_new_upload(tmp_path):
    first = make_image(tmp_path / "first.png")
    second = tmp_path / "second.png"
    second.write_bytes(first.read_bytes())
    ingest(first, tmp_path / "work")
    first.unlink()
    assert ingest(second, tmp_path / "work").source == second.resolve()


def test_load_roundtrip(video, tmp_path):
    done = ingest(video, tmp_path / "work")
    assert load(tmp_path / "work" / done.ad.content_hash) == done


def test_rejects_non_media(tmp_path):
    text = tmp_path / "notes.txt"
    text.write_text("not an ad")
    with pytest.raises(ValueError):
        ingest(text, tmp_path / "work")


def test_rejects_too_long(video, tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_module, "MAX_SECONDS", 2)
    with pytest.raises(ValueError, match="limit"):
        ingest(video, tmp_path / "work")


@pytest.fixture
def site(tmp_path):
    root = tmp_path / "site"
    root.mkdir()
    (root / "index.html").write_text(
        "<html><body style='margin:0'><p>Brightleaf Daily D supports normal immune function</p>"
        "<div style='height:2000px'></div></body></html>"
    )
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/index.html"
    server.shutdown()


def test_capture_page(site, tmp_path):
    pytest.importorskip("playwright")
    done = capture(site, tmp_path / "work")
    out = tmp_path / "work" / done.ad.content_hash
    assert (done.ad.media, done.ad.width) == ("page", 1280)
    assert done.ad.height >= 2000
    assert done.url == site
    assert "Brightleaf Daily D supports normal immune function" in done.text.read_text(encoding="utf-8")
    assert done.source == out.resolve() / "page.png"
    assert done.ad.content_hash == digest(done.source)
    assert load(out) == done


def test_capture_rejects_error_page(site, tmp_path):
    pytest.importorskip("playwright")
    with pytest.raises(ValueError, match="404"):
        capture(site.replace("index.html", "missing.html"), tmp_path / "work")
    assert not list((tmp_path / "work").glob("[0-9a-f]*"))


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/ad"])
def test_capture_rejects_non_http(url, tmp_path):
    with pytest.raises(ValueError, match="http"):
        capture(url, tmp_path / "work")
