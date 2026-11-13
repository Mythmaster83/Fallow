"""Build a static copy of Fallow that runs Python in the visitor's browser.

stlite loads Pyodide (Python compiled to WebAssembly) and runs the Streamlit
app inside the page. The host only serves files, so this fits Cloudflare's
free plan: no Python runs on Cloudflare.

Usage: python deploy/build_static.py [out_dir]   (default: dist)
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STLITE_VERSION = "1.11.0"

# Everything the app reads at runtime. Paths are relative to the repo root.
APP_GLOBS = [
    "app.py",
    "fallow_ui.py",
    ".streamlit/config.toml",
    "views/*.py",
    "larder/**/*.py",
    "fixtures/*.json",
]


def collect() -> list[str]:
    files: set[str] = set()
    for pattern in APP_GLOBS:
        for path in ROOT.glob(pattern):
            if path.is_file() and "__pycache__" not in path.parts:
                files.add(path.relative_to(ROOT).as_posix())
    return sorted(files)


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" />
  <title>Fallow</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@stlite/browser@{version}/build/stlite.css" />
  <style>
    html, body {{ margin: 0; background: #F6F5F2; }}
    #boot {{ font-family: system-ui, sans-serif; color: #55546A; text-align: center; padding-top: 30vh; }}
  </style>
</head>
<body>
  <div id="root"><div id="boot">Loading Fallow. The first visit downloads Python, so it takes a few seconds.</div></div>
  <script type="module">
    import {{ mount }} from "https://cdn.jsdelivr.net/npm/@stlite/browser@{version}/build/stlite.js";
    const files = Object.fromEntries({files}.map((p) => [p, {{ url: "/src/" + p }}]));
    files["data/.keep"] = "";
    mount(
      {{
        entrypoint: "app.py",
        // sqlite3 ships as a separate Pyodide package; it must be named.
        requirements: ["pydantic", "sqlite3"],
        files,
        env: {{ SENSOR_MODE: "mock" }},
      }},
      document.getElementById("root"),
    );

    // The views link to other screens with plain <a href="pantry">. In the
    // browser build a full page load restarts Python and always lands on the
    // dashboard, so route those clicks through Streamlit's own nav instead.
    document.addEventListener(
      "click",
      (event) => {{
        const link = event.target.closest && event.target.closest("a[href]");
        if (!link || link.target === "_blank") return;
        const match = /^\\/?([a-z][a-z0-9_-]*)?$/.exec(link.getAttribute("href"));
        if (!match) return;
        const path = "/" + (match[1] || "");
        const nav = Array.from(document.querySelectorAll("a[href]")).find(
          (a) => a !== link && a.hostname === "stlite.invalid" && new URL(a.href).pathname === path,
        );
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


def build(out: Path) -> None:
    # Overwrite in place: on Windows/OneDrive a locked folder cannot be removed.
    shutil.rmtree(out / "src", ignore_errors=True)
    files = collect()
    for rel in files:
        dest = out / "src" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dest)
    # config.toml points fonts at app/static/...; the page URL resolves that
    # relative to the site root, so serve the fonts there.
    shutil.copytree(ROOT / "static", out / "app" / "static", dirs_exist_ok=True)
    page = PAGE.format(version=STLITE_VERSION, files=json.dumps(files))
    (out / "index.html").write_text(page, encoding="utf-8")
    print(f"Built {len(files)} app files into {out}")


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist")
