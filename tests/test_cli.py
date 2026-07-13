"""CLI unit tests (no live cloud)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from dimplex_controller.cli import _redact, build_parser, main
from dimplex_controller.exceptions import DimplexConnectionError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _redact_params():
    return [
        ("abcdefghijklmnop", False, "abcd…mnop (16 chars)"),
        ("abcdefghijklmnop", True, "abcdefghijklmnop"),
        (None, False, "(none)"),
        ("short", False, "***"),
    ]


def _mock_client():
    """Build a mock DimplexControl for CLI command tests."""
    from unittest.mock import MagicMock

    client = MagicMock()
    client.auth = MagicMock()
    client.auth.get_access_token = AsyncMock(return_value="at")
    bundle = SimpleNamespace(
        refresh_token="rt",
        access_token="at",
        expires_at=9999,
        as_dict=lambda: {"refresh_token": "rt", "access_token": "at", "expires_at": 9999},
    )
    client.export_tokens.return_value = bundle
    return client


# ---------------------------------------------------------------------------
# _redact
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value,show,expected", _redact_params())
def test_redact(value, show, expected):
    assert _redact(value, show=show) == expected


# ---------------------------------------------------------------------------
# Parser structure
# ---------------------------------------------------------------------------


def test_parser_has_all_commands():
    parser = build_parser()
    # Reach into argparse internals to get subcommand names
    subparsers_action = next(a for a in parser._actions if hasattr(a, "_parser_class"))
    commands = set(subparsers_action.choices.keys())
    assert commands >= {"login", "hubs", "zones", "appliances", "status", "energy", "boost", "away", "eco"}


# ---------------------------------------------------------------------------
# No tokens → exit 2
# ---------------------------------------------------------------------------


def test_main_no_tokens_exits_2(monkeypatch):
    monkeypatch.delenv("DIMPLEX_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("DIMPLEX_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("DIMPLEX_TOKENS_FILE", raising=False)
    assert main(["hubs"]) == 2


# ---------------------------------------------------------------------------
# Subcommands with a mocked client
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_env(monkeypatch, tmp_path):
    """Set up token env so _load_tokens succeeds, and patch DimplexControl."""
    monkeypatch.setenv("DIMPLEX_REFRESH_TOKEN", "fake_rt")
    monkeypatch.delenv("DIMPLEX_TOKENS_FILE", raising=False)
    client = _mock_client()
    return client


def _run_cli(cli_env, argv):
    """Run the CLI main with a patched client."""
    with patch("dimplex_controller.cli.DimplexControl", return_value=cli_env):
        return main(argv)


def test_login(cli_env, capsys):
    code = _run_cli(cli_env, ["login"])
    assert code == 0
    out = capsys.readouterr().out
    assert "authenticated" in out


def test_hubs(cli_env, capsys):
    cli_env.get_hubs = AsyncMock(
        return_value=[
            SimpleNamespace(HubId="h1", FriendlyName="My Hub", Name="Hub 1", ConnectionState=1),
        ]
    )
    code = _run_cli(cli_env, ["hubs"])
    assert code == 0
    out = capsys.readouterr().out
    assert "h1" in out
    assert "My Hub" in out


def test_hubs_empty(cli_env, capsys):
    cli_env.get_hubs = AsyncMock(return_value=[])
    code = _run_cli(cli_env, ["hubs"])
    assert code == 0
    assert "(no hubs)" in capsys.readouterr().out


def test_zones(cli_env, capsys):
    cli_env.get_hubs = AsyncMock(
        return_value=[
            SimpleNamespace(HubId="h1", FriendlyName="Hub", Name="Hub", ConnectionState=1),
        ]
    )
    cli_env.get_hub_zones = AsyncMock(
        return_value=[
            SimpleNamespace(
                ZoneId="z1",
                ZoneName="Living Room",
                HubId="h1",
                Appliances=[
                    SimpleNamespace(ApplianceId="a1", FriendlyName="Heater", ApplianceModel="QRAD", ApplianceType="Q"),
                ],
            ),
        ]
    )
    code = _run_cli(cli_env, ["zones", "--hub", "h1", "-v"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Living Room" in out
    assert "a1" in out


def test_appliances(cli_env, capsys):
    cli_env.get_hubs = AsyncMock(
        return_value=[
            SimpleNamespace(HubId="h1", FriendlyName="Hub", Name="Hub", ConnectionState=1),
        ]
    )
    cli_env.get_hub_zones = AsyncMock(
        return_value=[
            SimpleNamespace(
                ZoneId="z1",
                ZoneName="LR",
                HubId="h1",
                Appliances=[
                    SimpleNamespace(ApplianceId="a1", FriendlyName="Rad", ApplianceModel="QRAD", ApplianceType="Q"),
                ],
            ),
        ]
    )
    code = _run_cli(cli_env, ["appliances"])
    assert code == 0
    assert "a1" in capsys.readouterr().out


def test_status(cli_env, capsys):
    from dimplex_controller.models import ApplianceStatus

    cli_env.get_appliance_overview = AsyncMock(
        return_value=[
            ApplianceStatus(HubId="h1", ApplianceId="a1", ZoneId="z1", RoomTemperature=20.5),
        ]
    )
    code = _run_cli(cli_env, ["status", "h1", "a1"])
    assert code == 0
    out = capsys.readouterr().out
    assert "20.5" in out


def test_status_empty(cli_env, capsys):
    cli_env.get_appliance_overview = AsyncMock(return_value=[])
    code = _run_cli(cli_env, ["status", "h1", "a1"])
    assert code == 0
    assert "offline" in capsys.readouterr().out


def test_energy(cli_env, capsys):
    cli_env.get_tsi_energy_report = AsyncMock(
        return_value=SimpleNamespace(HubId="h1", ApplianceTelemetryData={"a1": [1, 2, 3], "a2": []})
    )
    code = _run_cli(cli_env, ["energy", "h1", "--days", "7"])
    assert code == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["appliances"]["a1"] == 3
    assert parsed["appliances"]["a2"] == 0


def test_boost_requires_yes(cli_env, capsys):
    code = _run_cli(cli_env, ["boost", "h1", "a1"])
    assert code == 2
    assert "require --yes" in capsys.readouterr().err


def test_boost_with_yes(cli_env, capsys):
    cli_env.set_boost = AsyncMock()
    code = _run_cli(cli_env, ["boost", "h1", "a1", "--yes", "--temperature", "24", "--minutes", "30"])
    assert code == 0
    cli_env.set_boost.assert_awaited_once()
    kwargs = cli_env.set_boost.call_args
    assert kwargs.kwargs["temperature"] == 24.0
    assert kwargs.kwargs["duration_minutes"] == 30


def test_away_requires_yes(cli_env, capsys):
    code = _run_cli(cli_env, ["away", "h1", "a1"])
    assert code == 2


def test_away_with_yes(cli_env, capsys):
    cli_env.set_away = AsyncMock()
    code = _run_cli(cli_env, ["away", "h1", "a1", "--yes", "--clear"])
    assert code == 0
    cli_env.set_away.assert_awaited_once()
    assert cli_env.set_away.call_args.kwargs["enable"] is False


def test_eco_requires_yes(cli_env, capsys):
    code = _run_cli(cli_env, ["eco", "h1", "a1"])
    assert code == 2


def test_eco_with_yes(cli_env, capsys):
    cli_env.set_eco_start = AsyncMock()
    code = _run_cli(cli_env, ["eco", "h1", "a1", "--yes"])
    assert code == 0
    cli_env.set_eco_start.assert_awaited_once()


def test_api_error_exits_1(cli_env, capsys):
    cli_env.auth.get_access_token = AsyncMock(side_effect=DimplexConnectionError("boom"))
    code = _run_cli(cli_env, ["hubs"])
    assert code == 1
    assert "boom" in capsys.readouterr().err


def test_tokens_file(cli_env, capsys, tmp_path, monkeypatch):
    tokens_file = tmp_path / "tokens.json"
    tokens_file.write_text(json.dumps({"refresh_token": "rt", "access_token": "at", "expires_at": 9999}))
    monkeypatch.delenv("DIMPLEX_REFRESH_TOKEN", raising=False)
    code = _run_cli(cli_env, ["--tokens-file", str(tokens_file), "login"])
    assert code == 0
    # Tokens are saved back
    saved = json.loads(tokens_file.read_text())
    assert saved["refresh_token"] == "rt"


def test_show_tokens_flag(cli_env, capsys):
    code = _run_cli(cli_env, ["--show-tokens", "login"])
    assert code == 0
    out = capsys.readouterr().out
    # With --show-tokens short values show fully (not redacted as ***)
    assert "rt" in out
