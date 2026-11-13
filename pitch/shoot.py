"""Screenshot every Streamlit page and refresh the pitch deck.

Usage (from the repo root):

    .venv/bin/python pitch/shoot.py

What it does:
1. Starts ``streamlit run app.py`` headless on a free port, with a fresh
   database seeded from the sample fixture, SENSOR_MODE=mock and no LLM key,
   so every run produces the same shots.
2. Visits the dashboard plus every file in ``pages/`` and saves a PNG per page
   to ``pitch/screenshots/``.
3. Rewrites the ``SHOTS:*`` regions of ``pitch/index.html``:
   - slide 4 shows ``pitch/demo.mp4`` if it exists, otherwise the screenshots
     stepping in one by one;
   - slide 5 shows a feature grid with a thumbnail per feature.

New pages are picked up automatically. Add a caption to ``CAPTIONS`` and a
feature to ``FEATURES`` to give them nicer wording on the slides.
"""

from __future__ import annotations

import html
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Browser, Error as PlaywrightError, Page, Playwright, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PITCH = ROOT / "pitch"
SHOTS = PITCH / "screenshots"
DECK = PITCH / "index.html"

# Slug (screenshot file stem) -> caption on the demo slide, in demo-flow order.
CAPTIONS: dict[str, str] = {
    "dashboard": "1 · What spoils first, and what to cook tonight",
    "inventory": "2 · Every item, every location, ranked by urgency",
    "grow": "3 · Soil + weather + pantry gaps → what to plant",
    "cycle": "4 · Harvest → cook → compost → soil → seed",
}

# Feature cards on slide 5: (title, colour, blurb, screenshot slug).
FEATURES: list[tuple[str, str, str, str]] = [
    ("🔴 Spoilage tracking", "#e74c3c", "Knows what dies first, works offline.", "dashboard"),
    ("🟡 Meal planning", "#f39c12", "Meals from what's expiring. Never invents food.", "dashboard"),
    ("🟢 Grow advisor", "#4ecdc4", "Sensors + pantry gaps → what to plant now.", "grow"),
    ("🟣 Compost loop", "#9b59b6", "Scraps feed soil, soil feeds seeds, seeds feed you.", "cycle"),
]

HIDE_CHROME_CSS = """
header[data-testid="stHeader"], [data-testid="stToolbar"],
[data-testid="stDecoration"], [data-testid="stStatusWidget"],
.stDeployButton, footer { display: none !important; }
"""


@dataclass
class Target:
    slug: str
    url_path: str


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def discover_targets() -> list[Target]:
    targets = [Target("dashboard", "")]
    for page_file in sorted((ROOT / "pages").glob("*.py")):
        name = re.sub(r"^\d+_", "", page_file.stem)
        targets.append(Target(name.lower(), name))
    return targets


def wait_for_server(base: str, proc: subprocess.Popen[bytes], timeout: float = 60) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("Streamlit exited before it started serving.")
        try:
            with urllib.request.urlopen(f"{base}/_stcore/health", timeout=2) as resp:
                if resp.status == 200:
                    return
        except OSError:
            time.sleep(0.5)
    raise TimeoutError("Streamlit did not become healthy in time.")


def settle(page: Page) -> None:
    """Wait until Streamlit has finished running the script and drawing."""
    page.wait_for_selector('[data-testid="stMainBlockContainer"]', timeout=30_000)
    # Streamlit marks the app root with the script state; wait for the run to end.
    _ = page.wait_for_function(
        """() => {
            const app = document.querySelector('[data-testid="stApp"]');
            const state = app && app.getAttribute('data-test-script-state');
            const skeleton = document.querySelector('[data-testid="stSkeleton"]');
            return state === 'notRunning' && !skeleton;
        }""",
        timeout=30_000,
    )
    # Then wait until the main block stops changing for a moment.
    last = -1
    stable_since = time.time()
    deadline = time.time() + 20
    while time.time() < deadline:
        size = page.evaluate(
            "() => document.querySelector('[data-testid=\"stMainBlockContainer\"]').innerHTML.length"
        )
        if size != last:
            last, stable_since = size, time.time()
        elif time.time() - stable_since > 1.5:
            break
        page.wait_for_timeout(250)
    page.wait_for_timeout(1000)  # dataframes draw on a canvas after layout


def launch_browser(pw: Playwright) -> Browser:
    """Use Playwright's own Chromium, or the newest one already in the cache.

    A system-wide Playwright can expect a browser build that was never
    downloaded. Any recent cached Chromium drives fine, so try those before
    asking anyone to run ``playwright install``.
    """
    try:
        return pw.chromium.launch()
    except PlaywrightError:
        cache = Path.home() / ".cache" / "ms-playwright"
        candidates = sorted(
            cache.glob("chromium_headless_shell-*/*/chrome-headless-shell"),
            reverse=True,
        ) + sorted(cache.glob("chromium-*/*/chrome"), reverse=True)
        for exe in candidates:
            try:
                browser = pw.chromium.launch(executable_path=str(exe))
            except PlaywrightError:
                continue
            print(f"  using cached browser {exe}")
            return browser
        raise


def take_shots(base: str, targets: list[Target]) -> list[str]:
    SHOTS.mkdir(parents=True, exist_ok=True)
    taken: list[str] = []
    with sync_playwright() as pw:
        browser = launch_browser(pw)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
            color_scheme="dark",
        )
        page = context.new_page()
        for target in targets:
            page.goto(f"{base}/{target.url_path}", wait_until="networkidle")
            page.add_style_tag(content=HIDE_CHROME_CSS)
            settle(page)
            exceptions = page.locator('[data-testid="stException"]')
            if exceptions.count():
                print(f"  ! {target.slug}: page shows an exception", file=sys.stderr)
            out = SHOTS / f"{target.slug}.png"
            page.screenshot(path=str(out))
            taken.append(target.slug)
            print(f"  saved {out.relative_to(ROOT)}")
        browser.close()
    return taken


def ordered(slugs: list[str]) -> list[str]:
    known = [slug for slug in CAPTIONS if slug in slugs]
    return known + [slug for slug in slugs if slug not in CAPTIONS]


def demo_region(slugs: list[str]) -> str:
    if (PITCH / "demo.mp4").exists():
        return (
            '        <video class="demo-video" controls>\n'
            '          <source src="demo.mp4" type="video/mp4">\n'
            "        </video>\n"
        )
    lines = ['        <div class="r-stack shot-stack">']
    for index, slug in enumerate(ordered(slugs)):
        frag = "" if index == 0 else ' class="fragment"'
        caption = html.escape(CAPTIONS.get(slug, slug.title()))
        lines.append(
            f'          <div{frag} style="background:#0a0a0a">'
            f'<img src="screenshots/{slug}.png" alt="{slug}">'
            f'<div class="shot-caption">{caption}</div></div>'
        )
    lines.append("        </div>")
    return "\n".join(lines) + "\n"


def features_region(slugs: list[str]) -> str:
    lines = ['        <div class="feature-grid">']
    for title, colour, blurb, slug in FEATURES:
        if slug in slugs:
            visual = f'<img src="screenshots/{slug}.png" alt="{slug}">'
        else:
            visual = '<div class="todo">coming soon</div>'
        lines.append(
            f'          <div class="feature-card"><span style="color:{colour}"><b>{html.escape(title)}</b></span>'
            f" — {html.escape(blurb)}{visual}</div>"
        )
    lines.append("        </div>")
    return "\n".join(lines) + "\n"


CAD_DIR = PITCH / "cad"
CAD_IMAGES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
CAD_VIDEOS = {".mp4", ".webm"}


def cad_region() -> str:
    """Show whatever renders the CAD team dropped into pitch/cad/ (max 4)."""
    files = sorted(
        f for f in CAD_DIR.glob("*") if f.suffix.lower() in CAD_IMAGES | CAD_VIDEOS
    ) if CAD_DIR.is_dir() else []
    if not files:
        return (
            '        <div class="feature-card"><div class="todo">'
            "CAD renders go here — drop images or a short .mp4 into pitch/cad/"
            "</div></div>\n"
        )
    lines = ['        <div class="cad-grid">']
    for f in files[:4]:
        src = f"cad/{f.name}"
        caption = html.escape(f.stem.replace("_", " ").replace("-", " "))
        if f.suffix.lower() in CAD_VIDEOS:
            media = f'<video src="{src}" autoplay loop muted playsinline></video>'
        else:
            media = f'<img src="{src}" alt="{caption}">'
        lines.append(f"          <figure>{media}<figcaption>{caption}</figcaption></figure>")
    lines.append("        </div>")
    return "\n".join(lines) + "\n"


def replace_region(text: str, name: str, body: str) -> str:
    pattern = re.compile(
        rf"(<!-- SHOTS:{name}:START -->\n).*?(<!-- SHOTS:{name}:END -->)", re.DOTALL
    )
    if not pattern.search(text):
        raise ValueError(f"Deck is missing the SHOTS:{name} markers.")
    return pattern.sub(lambda m: m.group(1) + body + m.group(2), text)


def update_deck(slugs: list[str]) -> None:
    text = DECK.read_text(encoding="utf-8")
    text = replace_region(text, "DEMO", demo_region(slugs))
    text = replace_region(text, "FEATURES", features_region(slugs))
    text = replace_region(text, "CAD", cad_region())
    DECK.write_text(text, encoding="utf-8")
    print(f"  updated {DECK.relative_to(ROOT)}")


def main() -> None:
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory(prefix="fallow-shots-") as tmp:
        env = {
            **os.environ,
            "FALLOW_DB_PATH": str(Path(tmp) / "fallow.db"),
            "SENSOR_MODE": "mock",
            "LLM_API_KEY": "",
        }
        proc = subprocess.Popen(
            [
                sys.executable, "-m", "streamlit", "run", "app.py",
                "--server.headless", "true",
                "--server.port", str(port),
                "--browser.gatherUsageStats", "false",
                "--theme.base", "dark",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        try:
            wait_for_server(base, proc)
            print(f"Streamlit up on {base}")
            slugs = take_shots(base, discover_targets())
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
    update_deck(slugs)


if __name__ == "__main__":
    main()
