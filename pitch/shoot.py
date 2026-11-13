"""Screenshot every Streamlit page and refresh the pitch deck.

Usage (from the repo root):

    .venv/bin/python pitch/shoot.py

What it does:
1. Starts ``streamlit run app.py`` headless on a free port, with a fresh
   database seeded from the sample fixture, SENSOR_MODE=mock and no LLM key,
   so every run produces the same shots.
   It then walks part of the loop (plant kale, screen compost, cook carrots)
   so the Cycle page has history to show.
2. Visits the dashboard plus every file in ``views/`` and saves a PNG per page
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
# The story is needs-first: what you need, what the land offers, then the loop.
CAPTIONS: dict[str, str] = {
    "health": "1 · Know what you need: body, supplies, land",
    "farm": "2 · Read the environment: what to plant now",
    "harvest": "3 · Harvest a bed straight into the pantry",
    "pantry": "4 · Everything on hand, soonest to spoil first",
    "dashboard": "5 · What spoils first, and what to cook tonight",
    "recipes": "6 · Cook for what you need, from what you have",
    "cycle": "7 · Scraps to compost, compost back to soil",
}

# Extra shots of one tab inside a page: slug -> (url path, tab label).
TAB_SHOTS: dict[str, tuple[str, str]] = {
    "harvest": ("cycle", "Harvest"),
}

# Feature cards on slide 5, same order: (title, colour, blurb, screenshot slug).
FEATURES: list[tuple[str, str, str, str]] = [
    ("Know your needs", "#6B4FC8", "Vitals, reserves and land in one view.", "health"),
    ("Read the land", "#3F5A00", "Weather and soil pick what to plant.", "farm"),
    ("Harvest & store", "#2F7D5B", "Beds go straight into the pantry.", "harvest"),
    ("Spoilage first", "#B4361F", "Knows what dies first, offline.", "dashboard"),
    ("Cook from the shelf", "#9A6200", "Recipes never invent food.", "recipes"),
    ("Close the loop", "#6B4FC8", "Scraps feed soil, soil feeds seeds.", "cycle"),
]

# The top navigation lives in the header, so keep it; hide only dev chrome.
HIDE_CHROME_CSS = """
[data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], .stDeployButton, footer { display: none !important; }
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
    """Pages from ``views/``, using the same URL paths as ``st.navigation``."""
    targets = [Target("dashboard", "")]
    for page_file in sorted((ROOT / "views").glob("*.py")):
        if page_file.stem == "dashboard":
            continue
        targets.append(Target(page_file.stem, page_file.stem))
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
            color_scheme="light",
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
        for slug, (url_path, tab) in TAB_SHOTS.items():
            page.goto(f"{base}/{url_path}", wait_until="networkidle")
            page.add_style_tag(content=HIDE_CHROME_CSS)
            settle(page)
            tab_button = page.get_by_role("tab", name=tab)
            if not tab_button.count():
                print(f"  ! {slug}: no '{tab}' tab on /{url_path}", file=sys.stderr)
                continue
            tab_button.first.click()
            # Bring the tab bar to the top of the screen so its panel is in view.
            tab_button.first.evaluate("el => el.scrollIntoView({block: 'start'})")
            page.wait_for_timeout(1200)
            out = SHOTS / f"{slug}.png"
            page.screenshot(path=str(out))
            taken.append(slug)
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
            f'          <div{frag} style="background:var(--panel)">'
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
            f'          <div class="feature-card"><span style="color:{colour}">●</span> <b>{html.escape(title)}</b>'
            f'<div class="blurb">{html.escape(blurb)}</div>{visual}</div>'
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
            '        <div class="feature-card cad-empty"><div class="todo">'
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


def seed_demo_history(db_path: Path) -> None:
    """Walk part of the loop so the Cycle page has a story to show.

    Uses the same larder functions the pages call. Spinach and chicken are left
    alone so the dashboard still leads with them.
    """
    sys.path.insert(0, str(ROOT))
    from datetime import date

    from larder.lifecycle import advance, plant
    from larder.store import open_store

    today = date.today()
    store = open_store(db_path)

    def get(item_id: str):  # noqa: ANN202 - local helper
        item = store.get(item_id)
        if item is None:
            raise RuntimeError(f"Fixture is missing {item_id!r}; update seed_demo_history.")
        return item

    store.save(plant("kale", today, amendment=get("leaf-mould"), item_id="kale-bed"))
    store.save(advance(get("kitchen-compost"), "soil_amendment", today, note="screened the finished pile"))
    store.save(advance(get("carrots"), "cooked", today, note="roasted"))
    store.save(advance(get("carrots-scraps"), "compost", today, note="tops and peels on the pile"))


def main() -> None:
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory(prefix="fallow-shots-") as tmp:
        db_path = Path(tmp) / "fallow.db"
        seed_demo_history(db_path)
        env = {
            **os.environ,
            "FALLOW_DB_PATH": str(db_path),
            "SENSOR_MODE": "mock",
            "LLM_API_KEY": "",
        }
        proc = subprocess.Popen(
            [
                sys.executable, "-m", "streamlit", "run", "app.py",
                "--server.headless", "true",
                "--server.port", str(port),
                "--browser.gatherUsageStats", "false",
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
