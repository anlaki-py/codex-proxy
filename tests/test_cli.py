"""Tests for CLI utility commands and aliases."""

import sys

import pytest
from click.testing import CliRunner

from codex_proxy import cli
from codex_proxy.updater import ReleaseInfo, UpdateError


@pytest.mark.parametrize("argument", ["-h", "--help", "help"])
def test_help_aliases(argument: str) -> None:
    result = CliRunner().invoke(cli.main, [argument])

    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "Commands:" in result.output


@pytest.mark.parametrize("argument", ["-h", "--help"])
def test_serve_help_aliases_do_not_change_host(argument: str) -> None:
    result = CliRunner().invoke(cli.main, ["serve", argument])

    assert result.exit_code == 0
    assert "Usage: main serve [OPTIONS]" in result.output
    assert "--host TEXT" in result.output
    assert "-h, --host" not in result.output


@pytest.mark.parametrize(
    "command", ["accounts", "help", "login", "serve", "status", "switch", "update", "version"]
)
def test_short_help_is_available_on_every_subcommand(command: str) -> None:
    result = CliRunner().invoke(cli.main, [command, "-h"])

    assert result.exit_code == 0
    assert "Show this message and exit." in result.output


@pytest.mark.parametrize("argument", ["-v", "--version", "version"])
def test_version_aliases(argument: str) -> None:
    result = CliRunner().invoke(cli.main, [argument])

    assert result.exit_code == 0
    assert result.output == f"codex-proxy {cli.installed_version()}\n"


def test_update_reports_when_current_version_is_latest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "installed_version", lambda: "0.0.5")
    monkeypatch.setattr(
        cli,
        "fetch_latest_release",
        lambda: ReleaseInfo("0.0.5", "https://example.com/codex_proxy-0.0.5.whl"),
    )

    result = CliRunner().invoke(cli.main, ["update"])

    assert result.exit_code == 0
    assert result.output == "codex-proxy 0.0.5 is already up to date.\n"


def test_update_reports_release_lookup_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_lookup() -> ReleaseInfo:
        raise UpdateError("offline")

    monkeypatch.setattr(cli, "fetch_latest_release", fail_lookup)

    result = CliRunner().invoke(cli.main, ["update"])

    assert result.exit_code == 1
    assert "Error: offline" in result.output


def test_update_replaces_process_with_interpreter_pip(monkeypatch: pytest.MonkeyPatch) -> None:
    wheel_url = "https://example.com/codex_proxy-0.0.5-py3-none-any.whl"
    invoked: list[object] = []
    monkeypatch.setattr(cli, "installed_version", lambda: "0.0.4")
    monkeypatch.setattr(
        cli,
        "fetch_latest_release",
        lambda: ReleaseInfo("0.0.5", wheel_url),
    )

    def fail_exec(path: str, arguments: list[str]) -> None:
        invoked.extend([path, arguments])
        raise OSError("blocked for test")

    monkeypatch.setattr(cli.os, "execv", fail_exec)

    result = CliRunner().invoke(cli.main, ["update"])

    expected = [sys.executable, "-m", "pip", "install", "--upgrade", wheel_url]
    assert invoked == [sys.executable, expected]
    assert result.exit_code == 1
    assert "Updating codex-proxy 0.0.4 -> 0.0.5" in result.output
    assert "Could not start pip updater: blocked for test" in result.output
