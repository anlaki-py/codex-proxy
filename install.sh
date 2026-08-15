#!/usr/bin/env sh

set -eu

REPOSITORY="anlaki-py/codex-proxy"

PYTHON="${CODEX_PROXY_PYTHON:-}"
if [ -n "$PYTHON" ]; then
  :
elif command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "Python 3.11 or newer is required." >&2
  exit 1
fi

"$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else "Python 3.11 or newer is required.")'

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
"$PYTHON" -m pip install --upgrade "$WHEEL_URL"
echo "Installed codex-proxy with $PYTHON. Run 'codex-proxy login' to get started."
