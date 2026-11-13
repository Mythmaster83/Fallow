#!/usr/bin/env bash
# Package the pitch deck as a self-contained zip: dist/fallow-pitch.zip
# Unzip anywhere and open pitch/index.html — no install or network needed.
# Runs automatically after each commit if the post-commit hook is installed
# (see pitch/install_hook.sh).
set -euo pipefail
root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
cd "$root"
mkdir -p dist
out="dist/fallow-pitch.zip"
rm -f "$out"
zip -qr "$out" pitch \
  -x 'pitch/__pycache__/*' 'pitch/*.py' 'pitch/*.sh'
echo "pitch zip: $out ($(du -h "$out" | cut -f1))"
