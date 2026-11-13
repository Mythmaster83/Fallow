"""Turn the HTML pitch deck (web/pitch) into PowerPoint with no quality loss.

Each slide is the deck itself, captured at 3840x2160 by headless Chrome and
placed full-bleed. Every moving part is a real, embedded video sitting exactly
over its spot on the slide, set to start the moment the slide opens and loop:

- slide 2 pantry clock, 3 the loop, 4 the live demo, 5 the watch exploding
  with labels, 7 the probe exploding, 8 the assembly video, 9 the plant picker
  (clips from record_videos.py, plus the deck's own assembly video).

Two files come out:
- the main deck: fully self-contained, no internet needed;
- the clickable deck: the same, plus each interactive area and the QR codes
  link to that part of the live site (opens in the browser; needs internet).

Usage (from the repo root, with the static site served on :8502):
    python deploy/build_static.py
    python deploy/serve_spa.py 8502 dist &
    python pitch/ppt/record_videos.py            # writes dist/pitch-videos/
    python pitch/ppt/build_pptx.py               # writes the two .pptx files
Options: --reuse (skip re-capturing the slide stills)
"""

from __future__ import annotations

import html
import json
import re
import subprocess
import sys
from pathlib import Path

from lxml import etree
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

ROOT = Path(__file__).resolve().parents[2]
DECK = ROOT / "web" / "pitch" / "index.html"
MEDIA = ROOT / "web" / "pitch" / "media"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
CAPTURE_URL = "http://localhost:8502/web/pitch/_capture.html#{n}"
SITE = "https://fallow.aliahmedaziz08.workers.dev"
STAGE_W, STAGE_H = 1600, 900

# The deck's own assembly video on the "bom" slide (stage px). In the deck the
# title is drawn over the video; PowerPoint draws the video on top, so a strip
# of the captured title goes back over it (the video there is plain background).
ASSEMBLY = {"slide": 8, "file": MEDIA / "fallow-assembly-clean.mp4", "poster": MEDIA / "fallow-assembly-clean-poster.jpg",
            "box": (850.2, 25.7, 847.1, 847.1), "title_strip": (850.2, 104.0, 60.0, 80.0)}

# Clickable deck: what each interactive area opens (stage-px region, URL).
QR_S1 = (1055, 278.9, 290, 342.2)  # the QR card centred in the title slide's orbit
LINKS = {
    1: [(QR_S1, SITE + "/")],
    2: [((706, 70, 804, 760), SITE + "/web/pitch/#2")],
    3: [((90, 70, 1420, 760), SITE + "/web/pitch/#3")],
    4: [((554, 70, 956, 760), SITE + "/web/demo/")],
    5: [((554, 70, 956, 778.2), SITE + "/web/watch3d/")],
    7: [((554, 70, 956, 760), SITE + "/web/probe3d/")],
    9: [((90, 70, 1420, 760), SITE + "/web/pitch/#9")],
}

CAPTURE_CSS = """<style id="capture">
  #hud,#notes,.hint,#progress,#dots{display:none!important}
  #stage{border-radius:0!important;box-shadow:none!important}
  html,body{background:transparent!important;overflow:hidden!important}
  *{cursor:none!important}
  .toast:not(.show){visibility:hidden!important}
  .cmp tr.us .y{transform:scale(1)!important;transition:none!important}
  .cmp tr.us{opacity:1!important}
</style></head>"""


def slides_meta() -> list[tuple[str, str]]:
    """(section id, speaker notes) for every slide, in order."""
    text = DECK.read_text(encoding="utf-8")
    return [
        (m.group(1), html.unescape(m.group(2)))
        for m in re.finditer(r'<section class="slide" id="([^"]+)" data-notes="([^"]*)"', text)
    ]


def write_capture_page() -> None:
    """A copy of the deck that fills the window exactly and hides the controls."""
    page = (ROOT / "dist" / "web" / "pitch" / "index.html").read_text(encoding="utf-8")
    page = page.replace("Math.min(innerWidth / 1600, innerHeight / 900) * 0.96", "Math.min(innerWidth / 1600, innerHeight / 900)", 1)
    page = page.replace("</head>", CAPTURE_CSS, 1)
    # expose slide navigation for the video recorder (function declarations are hoisted)
    page = page.replace('  const slides = $$(".slide");', '  const slides = $$(".slide");\n  window.__go = (n) => go(n);', 1)
    (ROOT / "dist" / "web" / "pitch" / "_capture.html").write_text(page, encoding="utf-8")


def capture(n: int, out: Path) -> None:
    subprocess.run(
        [str(CHROME), "--headless=new", "--hide-scrollbars", "--mute-audio", "--use-angle=swiftshader",
         "--enable-unsafe-swiftshader", f"--window-size={STAGE_W},{STAGE_H}", "--force-device-scale-factor=2.4",
         "--virtual-time-budget=20000", f"--screenshot={out}", CAPTURE_URL.format(n=n)],
        check=True, capture_output=True,
    )


# PowerPoint's own "Start: Automatically, loop until stopped" for one video.
AUTOPLAY_TIMING = """<p:timing xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:tnLst><p:par>
<p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst>
<p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst>
<p:par><p:cTn id="3" fill="hold"><p:stCondLst><p:cond delay="indefinite"/><p:cond evt="onBegin" delay="0"><p:tn val="2"/></p:cond></p:stCondLst><p:childTnLst>
<p:par><p:cTn id="4" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>
<p:par><p:cTn id="5" presetID="1" presetClass="mediacall" presetSubtype="0" fill="hold" nodeType="afterEffect"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>
<p:cmd type="call" cmd="playFrom(0.0)"><p:cBhvr><p:cTn id="6" dur="1" fill="hold"/><p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cBhvr></p:cmd>
</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par>
</p:childTnLst></p:cTn>
<p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>
<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst></p:seq>
<p:video><p:cMediaNode vol="80000" mute="1"><p:cTn id="7" repeatCount="indefinite" fill="hold" display="0"><p:stCondLst><p:cond delay="indefinite"/></p:stCondLst></p:cTn><p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cMediaNode></p:video>
</p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>"""


def make_video_autoplay(slide, movie) -> None:  # noqa: ANN001
    """python-pptx makes the video play on click; make it start with the slide and loop."""
    old = slide._element.find(qn("p:timing"))  # noqa: SLF001
    new = etree.fromstring(AUTOPLAY_TIMING.format(spid=movie.shape_id))
    if old is not None:
        old.getparent().replace(old, new)
    else:
        slide._element.append(new)  # noqa: SLF001


def add_video(slide, px: float, video: Path, poster: Path, box: tuple, name: str):  # noqa: ANN001, ANN201
    x, y, w, h = box
    movie = slide.shapes.add_movie(
        str(video), Emu(int(x * px)), Emu(int(y * px)), Emu(int(w * px)), Emu(int(h * px)),
        poster_frame_image=str(poster), mime_type="video/mp4",
    )
    movie.name = name
    make_video_autoplay(slide, movie)
    return movie


def add_link(slide, px: float, box: tuple, url: str, label: str) -> None:  # noqa: ANN001
    """An invisible, clickable area over the region, plus a small "open live" tag."""
    x, y, w, h = box
    area = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(int(x * px)), Emu(int(y * px)), Emu(int(w * px)), Emu(int(h * px)))
    area.name = f"Link: {label}"
    area.fill.solid()
    area.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    # fully transparent but still clickable (a shape with no fill ignores clicks inside it)
    srgb = area.fill._xPr.find(qn("a:solidFill")).find(qn("a:srgbClr"))  # noqa: SLF001
    etree.SubElement(srgb, qn("a:alpha")).set("val", "0")
    area.line.fill.background()
    area.shadow.inherit = False
    area.click_action.hyperlink.address = url
    if label == "QR":
        return
    tw, th = 150, 34
    tag = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Emu(int((x + w - tw - 14) * px)), Emu(int((y + h - th - 14) * px)),
                                 Emu(int(tw * px)), Emu(int(th * px)))
    tag.name = f"Open live: {label}"
    tag.adjustments[0] = 0.5
    tag.fill.solid()
    tag.fill.fore_color.rgb = RGBColor(0x1E, 0x1E, 0x2A)
    tag.line.fill.background()
    tag.shadow.inherit = False
    tf = tag.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    run = tf.paragraphs[0].add_run()
    run.text = "Open live  \u2197"
    run.font.size, run.font.bold, run.font.name = Pt(11), True, "Arial"
    run.font.color.rgb = RGBColor(0xD7, 0xF2, 0x6E)
    tf.paragraphs[0].alignment = 2  # center
    tag.click_action.hyperlink.address = url


def build(shots: Path, videos: Path, out: Path, clickable: bool) -> None:
    meta = slides_meta()
    clips = json.loads((videos / "clips.json").read_text(encoding="utf-8")) if (videos / "clips.json").exists() else {}
    by_slide = {c["slide"]: (name, c) for name, c in clips.items()}

    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)  # 13.333 x 7.5 in, 16:9
    blank = prs.slide_layouts[6]
    px = prs.slide_width / STAGE_W  # EMU per stage pixel

    for n, (_sid, notes) in enumerate(meta, start=1):
        slide = prs.slides.add_slide(blank)
        shot = shots / f"slide-{n:02d}.png"
        pic = slide.shapes.add_picture(str(shot), 0, 0, prs.slide_width, prs.slide_height)
        pic.name = f"Slide {n}"
        if n in by_slide:
            name, clip = by_slide[n]
            add_video(slide, px, videos / f"{name}.mp4", videos / f"{name}.png", tuple(clip["region"]), name)
        if n == ASSEMBLY["slide"]:
            add_video(slide, px, ASSEMBLY["file"], ASSEMBLY["poster"], ASSEMBLY["box"], "Assembly video")
            sx, sy, sw, sh = ASSEMBLY["title_strip"]
            scale = Image.open(shot).width / STAGE_W
            strip_file = shots / f"slide-{n:02d}-title-strip.png"
            Image.open(shot).crop((round(sx * scale), round(sy * scale), round((sx + sw) * scale), round((sy + sh) * scale))).save(strip_file)
            over = slide.shapes.add_picture(str(strip_file), Emu(int(sx * px)), Emu(int(sy * px)), Emu(int(sw * px)), Emu(int(sh * px)))
            over.name = "Title (over video)"
        if clickable:
            for box, url in LINKS.get(n, []):
                add_link(slide, px, box, url, "QR" if box == QR_S1 else f"slide {n}")
        slide.notes_slide.notes_text_frame.text = notes

    cp = prs.core_properties
    cp.title = "Fallow: HackPerimeter pitch"
    cp.author = cp.last_modified_by = "Fallow team"
    cp.subject = cp.keywords = cp.comments = cp.category = ""
    prs.save(out)
    print(f"Wrote {out} ({len(meta)} slides{', clickable' if clickable else ''})")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    # absolute: Chrome resolves a relative --screenshot path against its own folder
    shots_dir = (Path(args[0]) if args else ROOT / "dist" / "pitch-shots").resolve()
    videos_dir = (Path(args[1]) if len(args) > 1 else ROOT / "dist" / "pitch-videos").resolve()
    if "--reuse" not in sys.argv:
        write_capture_page()
        shots_dir.mkdir(parents=True, exist_ok=True)
        for i in range(1, len(slides_meta()) + 1):
            capture(i, shots_dir / f"slide-{i:02d}.png")
    build(shots_dir, videos_dir, ROOT / "pitch" / "Fallow-Pitch-Final.pptx", clickable=False)
    build(shots_dir, videos_dir, ROOT / "pitch" / "Fallow-Pitch-Final-clickable.pptx", clickable=True)
