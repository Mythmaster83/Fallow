#!/usr/bin/env bash
# Install a git post-commit hook that rebuilds dist/fallow-pitch.zip.
# Run once per clone: pitch/install_hook.sh
set -euo pipefail
root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
hook="$root/.git/hooks/post-commit"
if [ -e "$hook" ] && ! grep -q make_zip.sh "$hook"; then
  echo "A different post-commit hook already exists at $hook; add this line to it:" >&2
  echo '  "$(git rev-parse --show-toplevel)/pitch/make_zip.sh" || true' >&2
  exit 1
fi
cat > "$hook" <<'HOOK'
#!/usr/bin/env bash
# Rebuild the pitch deck zip; never block a commit if it fails.
"$(git rev-parse --show-toplevel)/pitch/make_zip.sh" || true
HOOK
chmod +x "$hook"
echo "Installed $hook"
