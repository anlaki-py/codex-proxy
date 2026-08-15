#!/usr/bin/env sh

set -eu

REPOSITORY="anlaki-py/codex-proxy"

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "Python 3.11 or newer is required." >&2
  exit 1
fi

WHEEL_URL="${CODEX_PROXY_WHEEL_URL:-}"
if [ -z "$WHEEL_URL" ]; then
  WHEEL_URL="$($PYTHON - "$REPOSITORY" <<'PY'
import json
import sys
import urllib.request

repository = sys.argv[1]
request = urllib.request.Request(
    f"https://api.github.com/repos/{repository}/releases/latest",
    headers={"Accept": "application/vnd.github+json", "User-Agent": "codex-proxy-installer"},
)
with urllib.request.urlopen(request, timeout=30) as response:
    release = json.load(response)

wheels = [
    asset["browser_download_url"]
    for asset in release.get("assets", [])
    if asset.get("name", "").startswith("codex_proxy-")
    and asset.get("name", "").endswith("-py3-none-any.whl")
]
if len(wheels) != 1:
    raise SystemExit(f"Expected one codex-proxy wheel in the latest release, found {len(wheels)}")
print(wheels[0])
PY
)"
fi

echo "Installing the latest codex-proxy wheel..."
INSTALL_ROOT="${CODEX_PROXY_INSTALL_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/codex-proxy}"
BIN_DIR="${CODEX_PROXY_BIN_DIR:-${XDG_BIN_HOME:-$HOME/.local/bin}}"
VENV_DIR="$INSTALL_ROOT/venv"

mkdir -p "$INSTALL_ROOT" "$BIN_DIR"
"$PYTHON" -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install --upgrade --force-reinstall "$WHEEL_URL"
ln -sf "$VENV_DIR/bin/codex-proxy" "$BIN_DIR/codex-proxy"

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *)
    echo "Add $BIN_DIR to PATH to run codex-proxy directly:" >&2
    echo "  export PATH=\"$BIN_DIR:\$PATH\"" >&2
    ;;
esac

echo "Installed codex-proxy in $INSTALL_ROOT. Run 'codex-proxy login' to get started."
