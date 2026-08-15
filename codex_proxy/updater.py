"""Release discovery and self-update helpers."""

import json
import re
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

PACKAGE_NAME = "codex-proxy"
REPOSITORY = "anlaki-py/codex-proxy"
RELEASE_API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
VERSION_PATTERN = re.compile(r"^0\.0\.(\d+)$")


class UpdateError(RuntimeError):
    """Raised when release discovery or update preparation fails."""


@dataclass(frozen=True)
class ReleaseInfo:
    """Validated release metadata needed by the updater."""

    version: str
    wheel_url: str


def installed_version() -> str:
    """Return the installed distribution version."""
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError as exc:
        raise UpdateError("codex-proxy package metadata is unavailable") from exc


def _version_patch(value: str) -> int:
    match = VERSION_PATTERN.fullmatch(value)
    if match is None:
        raise UpdateError(f"unsupported release version: {value!r}")
    return int(match.group(1))


def update_available(current: str, latest: str) -> bool:
    """Return whether the validated latest release is newer than the installed version."""
    return _version_patch(latest) > _version_patch(current)


def parse_release(payload: Any) -> ReleaseInfo:
    """Validate a GitHub latest-release response."""
    if not isinstance(payload, dict):
        raise UpdateError("GitHub returned an invalid release object")

    tag_name = payload.get("tag_name")
    if not isinstance(tag_name, str) or not tag_name.startswith("v"):
        raise UpdateError("GitHub release is missing a valid version tag")
    release_version = tag_name.removeprefix("v")
    _version_patch(release_version)

    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise UpdateError("GitHub release is missing its asset list")

    expected_name = f"codex_proxy-{release_version}-py3-none-any.whl"
    wheels = [
        asset.get("browser_download_url")
        for asset in assets
        if isinstance(asset, dict)
        and asset.get("name") == expected_name
        and isinstance(asset.get("browser_download_url"), str)
    ]
    if len(wheels) != 1:
        raise UpdateError(
            f"expected one {expected_name} asset in the latest release; found {len(wheels)}"
        )

    wheel_url = wheels[0]
    parsed_url = urlparse(wheel_url)
    expected_path = (
        f"/{REPOSITORY}/releases/download/v{release_version}/{expected_name}"
    )
    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname != "github.com"
        or parsed_url.path != expected_path
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise UpdateError("GitHub returned an invalid wheel download URL")
    return ReleaseInfo(version=release_version, wheel_url=wheel_url)


def fetch_latest_release() -> ReleaseInfo:
    """Fetch and validate the latest GitHub release."""
    request = Request(
        RELEASE_API_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "codex-proxy-updater"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except HTTPError as exc:
        raise UpdateError(
            f"GitHub release lookup failed with HTTP {exc.code}: {exc.reason}"
        ) from exc
    except URLError as exc:
        raise UpdateError(f"GitHub release lookup failed: {exc.reason}") from exc
    except (json.JSONDecodeError, UnicodeError, OSError) as exc:
        raise UpdateError(f"GitHub returned an unusable release response: {exc}") from exc
    return parse_release(payload)


def pip_update_command(release: ReleaseInfo) -> list[str]:
    """Build the interpreter-qualified pip command used for self-update."""
    return [sys.executable, "-m", "pip", "install", "--upgrade", release.wheel_url]
