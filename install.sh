#!/usr/bin/env sh

set -eu

REPOSITORY="anlaki-py/codex-proxy"

fail() {
  printf '\nError: %s\n' "$1" >&2
  exit 1
}

try_python() {
  candidate="$1"
  if [ ! -x "$candidate" ] && ! command -v "$candidate" >/dev/null 2>&1; then
    return 1
  fi

  if ! candidate_version="$("$candidate" -c 'import platform; print(platform.python_version())' 2>/dev/null)"; then
    printf 'Skipping %s: the interpreter could not run.\n' "$candidate" >&2
    return 1
  fi
  if ! "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    printf 'Skipping %s: Python %s is older than 3.11.\n' "$candidate" "$candidate_version" >&2
    return 1
  fi
  if ! "$candidate" -m pip --version >/dev/null 2>&1; then
    printf 'Skipping %s: pip is unavailable.\n' "$candidate" >&2
    return 1
  fi

  PYTHON="$candidate"
  return 0
}

PYTHON=""
requested_python="${CODEX_PROXY_PYTHON:-}"
if [ -n "$requested_python" ]; then
  if ! try_python "$requested_python"; then
    fail "CODEX_PROXY_PYTHON is not a working Python 3.11+ interpreter with pip: $requested_python"
  fi
else
  for candidate in python3.14 python3.13 python3.12 python3.11 python3 python; do
    if try_python "$candidate"; then
      break
    fi
  done
  if [ -z "$PYTHON" ]; then
    fail "No working Python 3.11 or newer with pip was found."
  fi
fi

WHEEL_URL="${CODEX_PROXY_WHEEL_URL:-}"
if [ -z "$WHEEL_URL" ]; then
  if ! WHEEL_URL="$("$PYTHON" - "$REPOSITORY" <<'PY'
import json
import sys
from urllib.error import HTTPError, URLError
import urllib.request

repository = sys.argv[1]
request = urllib.request.Request(
    f"https://api.github.com/repos/{repository}/releases/latest",
    headers={"Accept": "application/vnd.github+json", "User-Agent": "codex-proxy-installer"},
)
try:
    with urllib.request.urlopen(request, timeout=30) as response:
        release = json.load(response)
except HTTPError as exc:
    raise SystemExit(f"GitHub release lookup failed with HTTP {exc.code}: {exc.reason}") from exc
except URLError as exc:
    raise SystemExit(f"GitHub release lookup failed: {exc.reason}") from exc
except (json.JSONDecodeError, UnicodeError, OSError) as exc:
    raise SystemExit(f"GitHub returned an unusable release response: {exc}") from exc

if not isinstance(release, dict):
    raise SystemExit("GitHub returned an invalid release object")
assets = release.get("assets", [])
if not isinstance(assets, list):
    raise SystemExit("GitHub returned an invalid release asset list")

wheels = [
    asset.get("browser_download_url")
    for asset in assets
    if isinstance(asset, dict)
    and isinstance(asset.get("name"), str)
    and asset["name"].startswith("codex_proxy-")
    and asset["name"].endswith("-py3-none-any.whl")
    and isinstance(asset.get("browser_download_url"), str)
    and asset["browser_download_url"].startswith("https://")
]
if len(wheels) != 1:
    raise SystemExit(f"Expected one codex-proxy wheel in the latest release, found {len(wheels)}")
print(wheels[0])
PY
)"; then
    fail "Could not determine the latest codex-proxy wheel. Check the error above and retry."
  fi
fi

echo "Installing the latest codex-proxy wheel..."
if ! "$PYTHON" -m pip install --upgrade "$WHEEL_URL"; then
  fail "pip could not install codex-proxy. Check network access and Python permissions."
fi

if ! INSTALLED_VERSION="$("$PYTHON" -c "from importlib.metadata import version; print(version('codex-proxy'))")"; then
  fail "pip completed, but codex-proxy is not importable from $PYTHON."
fi

if ! EXECUTABLE="$("$PYTHON" - <<'PY'
import os
from pathlib import Path
import shutil
import sysconfig

schemes = (sysconfig.get_default_scheme(), sysconfig.get_preferred_scheme("user"))
executable_name = "codex-proxy.exe" if os.name == "nt" else "codex-proxy"
for scheme in dict.fromkeys(schemes):
    candidate = Path(sysconfig.get_path("scripts", scheme=scheme)) / executable_name
    if candidate.is_file() and os.access(candidate, os.X_OK):
        print(candidate.as_posix())
        raise SystemExit

candidate = shutil.which("codex-proxy")
if candidate:
    print(candidate)
PY
)"; then
  fail "Installed codex-proxy, but failed to inspect its executable location."
fi
if [ -z "$EXECUTABLE" ]; then
  fail "Installed codex-proxy $INSTALLED_VERSION, but its executable was not created."
fi
if ! "$EXECUTABLE" --help >/dev/null 2>&1; then
  fail "Installed executable failed its startup check: $EXECUTABLE"
fi

EXECUTABLE_DIR="${EXECUTABLE%/*}"
case ":$PATH:" in
  *":$EXECUTABLE_DIR:"*) ;;
  *)
    printf '\nInstalled successfully, but %s is not on PATH.\n' "$EXECUTABLE_DIR" >&2
    printf 'Add this line to your shell profile, then open a new terminal:\n' >&2
    printf '  export PATH="%s:$PATH"\n' "$EXECUTABLE_DIR" >&2
    ;;
esac

echo "Installed codex-proxy $INSTALLED_VERSION with $PYTHON. Run 'codex-proxy login' to get started."
