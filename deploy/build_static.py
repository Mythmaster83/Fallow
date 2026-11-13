"""Build the Fallow website as static files for Cloudflare (free plan).

    dist/
      index.html          landing page: "Watch the presentation" / "Try the live demo"
      web/                the pitch deck, clickable demo, 3D watch and probe (as-is)
      app/index.html      the real Fallow app, running in the visitor's browser
      app/src/...         the app's Python files, fetched by the page
      app/app/static/...  fonts and logo (the app links them as app/static/...)

The live app uses stlite: Pyodide (Python compiled to WebAssembly) runs the
Streamlit app inside the page, so the host only serves files and no Python
runs on Cloudflare.

Usage: python deploy/build_static.py [out_dir]   (default: dist)
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STLITE_VERSION = "1.11.0"
APP_PREFIX = "/app/"

# Everything the app reads at runtime. Paths are relative to the repo root.
APP_GLOBS = [
    "app.py",
    "fallow_ui.py",
    ".streamlit/config.toml",
    "views/*.py",
    "larder/**/*.py",
    "fixtures/*.json",
    "static/*.svg",
    "static/*.png",
]


def collect() -> list[str]:
    files: set[str] = set()
    for pattern in APP_GLOBS:
        for path in ROOT.glob(pattern):
            if path.is_file() and "__pycache__" not in path.parts:
                files.add(path.relative_to(ROOT).as_posix())
    return sorted(files)


APP_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>Fallow · Live demo</title>
  <link rel="icon" href="{prefix}src/static/fallow-logo-app-192.png" />
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@stlite/browser@{version}/build/stlite.css" />
  <style>
    html, body {{ margin: 0; background: #F3F1F7; }}
    #boot {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif; color: #4A4959;
      min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px; }}
    #boot img {{ width: 56px; height: 56px; border-radius: 14px; }}
    #boot b {{ font-size: 17px; color: #17171F; }}
    #boot span {{ font-size: 14px; opacity: .75; }}
  </style>
</head>
<body>
  <div id="root"><div id="boot"><img src="{prefix}src/static/fallow-logo-app-192.png" alt="" />
    <b>Starting Fallow</b><span>The first visit downloads Python, so it takes a few seconds.</span></div></div>
  <script type="module">
    import {{ mount }} from "https://cdn.jsdelivr.net/npm/@stlite/browser@{version}/build/stlite.js";
    // Each URL carries the file's content hash, so a new deploy never mixes
    // cached old files with new ones.
    const files = Object.fromEntries(Object.entries({files}).map(([p, v]) => [p, {{ url: "{prefix}src/" + p + "?v=" + v }}]));
    files["data/.keep"] = "";
    mount(
      {{
        entrypoint: "app.py",
        // sqlite3 ships as a separate Pyodide package; it must be named.
        requirements: ["pydantic", "sqlite3"],
        files,
        // Real weather, soil and air from Open-Meteo; falls back to the sample offline.
        env: {{ SENSOR_MODE: "live" }},
        disableProgressToasts: true,
      }},
      document.getElementById("root"),
    );

    // Views link to other screens with plain <a href="pantry">. A full page
    // load would restart Python, so route those clicks through the app's nav.
    document.addEventListener(
      "click",
      (event) => {{
        const link = event.target.closest && event.target.closest("a[href]");
        if (!link || link.target === "_blank") return;
        const match = /^\\/?([a-z][a-z0-9_-]*)?$/.exec(link.getAttribute("href"));
        if (!match) return;
        const target = match[1] || "";
        const slug = (a) =>
          a.hostname === "stlite.invalid"
            ? new URL(a.href).pathname.replace(/^\\//, "")
            : (a.getAttribute("href") || "").replace(/^\\//, "");
        const nav = Array.from(
          document.querySelectorAll('a[data-testid="stPageLink-NavLink"], a[href*="stlite.invalid"]'),
        ).find((a) => a !== link && slug(a) === target);
        if (!nav) return;
        event.preventDefault();
        nav.click();
        window.scrollTo(0, 0);
      }},
      true,
    );
  </script>
</body>
</html>
"""


def _copy_tree(src: Path, dest: Path) -> None:
    shutil.copytree(src, dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))


def build(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    # Overwrite in place: on Windows/OneDrive a locked folder cannot be removed.
    shutil.rmtree(out / "app" / "src", ignore_errors=True)

    # 1. Landing page and its assets.
    _copy_tree(ROOT / "site", out)

    # 2. The pitch deck and the web demos, unchanged at /web/ (the deck finds
    #    ../demo, ../watch3d and ../probe3d from /web/pitch/).
    _copy_tree(ROOT / "web", out / "web")

    # 3. The live app under /app/.
    files = collect()
    for rel in files:
        dest = out / "app" / "src" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dest)
    _copy_tree(ROOT / "static", out / "app" / "app" / "static")
    hashes = {rel: hashlib.sha1((ROOT / rel).read_bytes()).hexdigest()[:10] for rel in files}
    page = APP_PAGE.format(version=STLITE_VERSION, files=json.dumps(hashes), prefix=APP_PREFIX)
    (out / "app" / "index.html").write_text(page, encoding="utf-8")

    print(f"Built the site into {out}: landing, web/, and {len(files)} app files under app/")


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist")
