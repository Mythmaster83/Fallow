"""Record the deck's interactive slides as looping videos for the PowerPoint.

Every clip is recorded from the real deck (web/pitch, served by the static
site on :8502) in Chrome, then cropped to the part of the slide that moves, so
the video sits exactly over the 4K still in PowerPoint.

- Slide 5 (watch) uses the 3D viewer's own film mode: frame-exact, the watch
  explodes, every part gets its label, then it comes back together.
- The other clips are recorded in real time while a script clicks through the
  slide's interaction, and end by resetting it so they loop cleanly.

Usage (from the repo root, with the site served on :8502):
    python pitch/ppt/record_videos.py [out_dir]
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
URL = "http://localhost:8502/web/pitch/_capture.html#{n}"
DSF = 2  # the deck is rendered at 3200 x 1800 (the stage scales up to fill it)
FPS = 30
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
CHROME_ARGS = ["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist", "--autoplay-policy=no-user-gesture-required"]

# Stage-pixel regions (x, y, w, h), measured from the deck.
FULL = (0, 0, 1600, 900)
CLIPS = {
    "s2-pantry-clock": {"slide": 2, "region": (706, 70, 804, 760)},
    "s3-loop": {"slide": 3, "region": FULL},
    "s4-live-demo": {"slide": 4, "region": (554, 70, 956, 760)},
    "s5-watch": {"slide": 5, "region": (554, 70, 956, 778.2)},
    "s7-probe": {"slide": 7, "region": (554, 70, 956, 760)},
    "s9-plant": {"slide": 9, "region": FULL},
}


# ---- interaction scripts: list of (wait ms before, action) -------------------------
def _click(sel: str):
    return lambda page: page.evaluate(f"document.querySelector({json.dumps(sel)}).click()")


def _frame_click(frame_sel: str, sel: str):
    def act(page: Page) -> None:
        page.frame_locator(frame_sel).locator(sel).first.click(timeout=4000)
    return act


def _set_range(sel: str, value: int):
    return lambda page: page.evaluate(
        f"(() => {{ const r = document.querySelector({json.dumps(sel)}); r.value = {value}; "
        "r.dispatchEvent(new Event('input', {bubbles: true})); r.dispatchEvent(new Event('change', {bubbles: true})); })()"
    )


def _months(seq: list[int], gap: int):
    return [(gap, _click(f'#months button[data-m="{m}"]')) for m in seq]


SCRIPTS = {
    "s2-pantry-clock": [
        (900, _click("#clockPlay")),            # without Fallow: food spoils day by day
        (6600, _click('#s2 .toggle button[data-v="1"]')),
        (700, _set_range("#day", 0)),
        (500, _click("#clockPlay")),            # with Fallow: eaten in time
        (6900, _click('#s2 .toggle button[data-v="0"]')),
        (300, _set_range("#day", 0)),
        (900, None),
    ],
    "s3-loop": [(900, _click("#loopPlay")), (10600, _click("#loopReset")), (1200, None)],  # 5 steps x 1.3 s, then the 3.6 s popup
    "s4-live-demo": [
        (1500, None),
        (1200, _frame_click("#s4 iframe", "text=Watch")),
        (3200, _frame_click("#s4 iframe", "text=Website")),
        (3600, _frame_click("#s4 iframe", "text=Phone")),
        (2400, None),
    ],
    "s7-probe": [
        (1800, _frame_click("#stake iframe", "#explode")),   # explode with labels while it turns
        (5200, _frame_click("#stake iframe", "#explode")),   # back together
        (2600, None),
    ],
    "s9-plant": [
        *_months([1, 3, 5, 7, 9], 900),
        (900, _click("#frost")),
        (1100, _set_range("#moist", 15)),
        (1100, _set_range("#moist", 45)),
        (900, _click("#frost")),
        (700, _click('#months button[data-m="11"]')),
        (1300, None),
    ],
}


# ---- encoding -----------------------------------------------------------------------
def _encode(frames: list[tuple[float, bytes]], region: tuple, out: Path, ext: str = "jpg") -> None:
    """frames: (seconds, image bytes). Variable-rate frames become a constant-rate H.264 loop."""
    # Scale the stage region to the frames' real size (screencast may deliver less than DSF).
    import io

    from PIL import Image
    fw, fh = Image.open(io.BytesIO(frames[0][1])).size
    k = fw / 1600
    x, y, w, h = (round(v * k) for v in region)
    w, h = min(w, fw - x), min(h, fh - y)
    w, h = w - w % 2, h - h % 2
    with tempfile.TemporaryDirectory() as tmp:
        tmpd = Path(tmp)
        lines = []
        for i, (t, data) in enumerate(frames):
            f = tmpd / f"f{i:05d}.{ext}"
            f.write_bytes(data)
            # real time between frames; the fps filter resamples to a steady 30 fps.
            # (Never stretch short frames to 1/FPS: that turns the clip into slow motion.)
            dur = (frames[i + 1][0] - t) if i + 1 < len(frames) else 1 / FPS
            lines += [f"file '{f.as_posix()}'", f"duration {max(dur, 0.001):.4f}"]
        lines.append(f"file '{(tmpd / f'f{len(frames) - 1:05d}.{ext}').as_posix()}'")
        (tmpd / "list.txt").write_text("\n".join(lines), encoding="utf-8")
        subprocess.run(
            [FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(tmpd / "list.txt"),
             "-vf", f"crop={w}:{h}:{x}:{y},fps={FPS}", "-c:v", "libx264", "-preset", "slow", "-crf", "14",
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
            check=True,
        )
        poster = out.with_suffix(".png")
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(out), "-frames:v", "1", str(poster)], check=True)


def _open(browser, n: int) -> Page:  # noqa: ANN001
    page = browser.new_page(viewport={"width": 1600 * DSF, "height": 900 * DSF}, device_scale_factor=1)
    page.goto(URL.format(n=n))
    page.wait_for_timeout(3500)  # slide transition, iframes and 3D models load
    return page


def record_live(browser, name: str, out_dir: Path) -> Path:  # noqa: ANN001
    clip = CLIPS[name]
    page = _open(browser, clip["slide"])
    cdp = page.context.new_cdp_session(page)
    frames: list[tuple[float, bytes]] = []

    def on_frame(p: dict) -> None:
        frames.append((p["metadata"]["timestamp"], base64.b64decode(p["data"])))
        try:
            cdp.send("Page.screencastFrameAck", {"sessionId": p["sessionId"]})
        except Exception:  # a late frame after the page closed: nothing to acknowledge
            pass

    cdp.on("Page.screencastFrame", on_frame)
    cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 95, "everyNthFrame": 1, "maxWidth": 1600 * DSF, "maxHeight": 900 * DSF})
    for wait, act in SCRIPTS[name]:
        page.wait_for_timeout(wait)
        if act:
            act(page)
    page.wait_for_timeout(200)
    cdp.send("Page.stopScreencast")
    page.close()
    t0 = frames[0][0]
    out = out_dir / f"{name}.mp4"
    _encode([(t - t0, d) for t, d in frames], clip["region"], out)
    import io
    from PIL import Image
    size = Image.open(io.BytesIO(frames[0][1])).size
    print(f"{name}: {len(frames)} frames ({size[0]}x{size[1]}) over {frames[-1][0] - t0:.1f}s -> {out.name}")
    return out


def record_watch_film(browser, out_dir: Path) -> Path:  # noqa: ANN001
    """Frame-exact: drive the watch viewer's own film timeline inside the slide."""
    name, clip = "s5-watch", CLIPS["s5-watch"]
    page = browser.new_page(viewport={"width": 1600 * DSF, "height": 900 * DSF}, device_scale_factor=1)
    page.goto(URL.format(n=1))
    page.wait_for_timeout(800)
    # Point the slide's watch frame at the film mode (labels on, no captions), then open slide 5.
    page.evaluate("""document.querySelector('#s5 iframe').dataset.src = 'watch3d/index.html?film=1&clean=1&bg=14141c&zoom=1.1'""")
    page.evaluate("window.__go(4)")
    frame = None
    for _ in range(60):
        page.wait_for_timeout(500)
        frame = next((f for f in page.frames if "watch3d" in f.url), None)
        if frame and frame.evaluate("window.__filmReady === true"):
            break
    assert frame is not None, "watch viewer did not load"
    page.wait_for_timeout(800)
    x, y, w, h = clip["region"]
    frames: list[tuple[float, bytes]] = []
    seconds = 12.4
    for i in range(int(seconds * FPS)):
        frame.evaluate(f"window.__film({i / FPS:.4f})")
        png = page.screenshot(type="png")
        frames.append((i / FPS, png))
    page.close()
    out = out_dir / f"{name}.mp4"
    _encode(frames, clip["region"], out, ext="png")
    print(f"{name}: {len(frames)} film frames -> {out.name}")
    return out


def main(out_dir: Path, only: list[str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True, args=CHROME_ARGS)
        for name in CLIPS:
            if only and name not in only:
                continue
            if name == "s5-watch":
                record_watch_film(browser, out_dir)
            else:
                record_live(browser, name, out_dir)
        browser.close()
    (out_dir / "clips.json").write_text(json.dumps(CLIPS, indent=2), encoding="utf-8")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = Path(args[0]) if args else ROOT / "dist" / "pitch-videos"
    main(out, [a[2:] for a in sys.argv[1:] if a.startswith("--") and a[2:] in CLIPS])
