"""Tests for release discovery and update command construction."""

import io
import json
import sys
from typing import Any
from urllib.error import URLError

import pytest

from codex_proxy import updater


def _release_payload(version: str = "0.0.5") -> dict[str, Any]:
    wheel_name = f"codex_proxy-{version}-py3-none-any.whl"
    return {
        "tag_name": f"v{version}",
        "assets": [
            {
                "name": wheel_name,
                "browser_download_url": (
                    f"https://github.com/anlaki-py/codex-proxy/releases/download/"
                    f"v{version}/{wheel_name}"
                ),
            }
        ],
    }


def test_parse_release_accepts_exact_versioned_wheel() -> None:
    release = updater.parse_release(_release_payload())

    assert release.version == "0.0.5"
    assert release.wheel_url.endswith("/codex_proxy-0.0.5-py3-none-any.whl")


@pytest.mark.parametrize("tag_name", [None, "0.0.5", "v1.0.0", "v0.0.beta"])
def test_parse_release_rejects_invalid_tag(tag_name: object) -> None:
    payload = _release_payload()
    payload["tag_name"] = tag_name

    with pytest.raises(updater.UpdateError):
        updater.parse_release(payload)


@pytest.mark.parametrize("asset_count", [0, 2])
def test_parse_release_requires_one_exact_wheel(asset_count: int) -> None:
    payload = _release_payload()
    payload["assets"] = payload["assets"] * asset_count

    with pytest.raises(updater.UpdateError, match="expected one"):
        updater.parse_release(payload)


def test_parse_release_rejects_non_https_wheel() -> None:
    payload = _release_payload()
    payload["assets"][0]["browser_download_url"] = "file:///tmp/codex_proxy.whl"

    with pytest.raises(updater.UpdateError, match="invalid wheel download URL"):
        updater.parse_release(payload)


def test_parse_release_rejects_wheel_from_another_host() -> None:
    payload = _release_payload()
    payload["assets"][0]["browser_download_url"] = (
        "https://example.com/codex_proxy-0.0.5-py3-none-any.whl"
    )

    with pytest.raises(updater.UpdateError, match="invalid wheel download URL"):
        updater.parse_release(payload)


def test_update_available_compares_release_numbers_numerically() -> None:
    assert updater.update_available("0.0.9", "0.0.10") is True
    assert updater.update_available("0.0.10", "0.0.10") is False
    assert updater.update_available("0.0.11", "0.0.10") is False


def test_update_available_rejects_unsupported_version() -> None:
    with pytest.raises(updater.UpdateError, match="unsupported release version"):
        updater.update_available("1.0.0", "0.0.5")


def test_fetch_latest_release_reads_json_response(monkeypatch: pytest.MonkeyPatch) -> None:
    response = io.BytesIO(json.dumps(_release_payload()).encode())
    monkeypatch.setattr(updater, "urlopen", lambda request, timeout: response)

    assert updater.fetch_latest_release().version == "0.0.5"


def test_fetch_latest_release_reports_network_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_request(request: object, timeout: int) -> None:
        raise URLError("offline")

    monkeypatch.setattr(updater, "urlopen", fail_request)

    with pytest.raises(updater.UpdateError, match="offline"):
        updater.fetch_latest_release()


def test_pip_update_command_uses_running_interpreter() -> None:
    release = updater.parse_release(_release_payload())

    assert updater.pip_update_command(release) == [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        release.wheel_url,
    ]
