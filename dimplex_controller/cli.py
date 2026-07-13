"""Command-line interface for smoke-testing Dimplex cloud access.

Tokens are read from environment variables by default:

* ``DIMPLEX_REFRESH_TOKEN``
* ``DIMPLEX_ACCESS_TOKEN`` (optional)
* ``DIMPLEX_EXPIRES_AT`` (optional unix timestamp)

Or from a JSON file via ``--tokens-file`` (keys: refresh_token, access_token,
expires_at). Secrets are never printed unless ``--show-tokens`` is passed.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import aiohttp

from .auth import TokenBundle
from .client import DimplexControl
from .exceptions import DimplexError

_CoroFactory = Callable[[DimplexControl], Awaitable[int]]


def _load_tokens(path: Path | None) -> TokenBundle:
    if path is not None:
        data = json.loads(path.read_text(encoding="utf-8"))
        return TokenBundle.from_mapping(data)
    return TokenBundle(
        refresh_token=os.environ.get("DIMPLEX_REFRESH_TOKEN"),
        access_token=os.environ.get("DIMPLEX_ACCESS_TOKEN"),
        expires_at=float(os.environ.get("DIMPLEX_EXPIRES_AT") or 0),
    )


def _save_tokens(path: Path, bundle: TokenBundle) -> None:
    path.write_text(json.dumps(bundle.as_dict(), indent=2) + "\n", encoding="utf-8")
    with contextlib.suppress(OSError):
        path.chmod(0o600)


def _redact(value: str | None, *, show: bool) -> str:
    if not value:
        return "(none)"
    if show:
        return value
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}…{value[-4:]} ({len(value)} chars)"


async def _with_client(
    args: argparse.Namespace,
    coro_factory: _CoroFactory,
) -> int:
    tokens = _load_tokens(Path(args.tokens_file) if args.tokens_file else None)
    if not tokens.refresh_token and not tokens.access_token:
        print(
            "error: no tokens — set DIMPLEX_REFRESH_TOKEN or pass --tokens-file",
            file=sys.stderr,
        )
        return 2

    async with aiohttp.ClientSession() as session:
        client = DimplexControl(session, token_bundle=tokens)
        try:
            await client.auth.get_access_token()
            if args.tokens_file:
                _save_tokens(Path(args.tokens_file), client.export_tokens())
            return await coro_factory(client)
        except DimplexError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1


async def cmd_login(client: DimplexControl, args: argparse.Namespace) -> int:
    """Validate tokens and optionally write them back."""
    bundle = client.export_tokens()
    print("authenticated")
    print(f"  refresh_token: {_redact(bundle.refresh_token, show=args.show_tokens)}")
    print(f"  access_token:  {_redact(bundle.access_token, show=args.show_tokens)}")
    print(f"  expires_at:    {bundle.expires_at}")
    if args.tokens_file:
        _save_tokens(Path(args.tokens_file), bundle)
        print(f"  wrote:         {args.tokens_file}")
    return 0


async def cmd_hubs(client: DimplexControl, args: argparse.Namespace) -> int:
    hubs = await client.get_hubs()
    for hub in hubs:
        name = hub.FriendlyName or hub.Name or "(unnamed)"
        print(f"{hub.HubId}\t{name}\tconnection={hub.ConnectionState}")
    if not hubs:
        print("(no hubs)")
    return 0


async def cmd_zones(client: DimplexControl, args: argparse.Namespace) -> int:
    hubs = await client.get_hubs()
    hub_id = args.hub or (hubs[0].HubId if hubs else None)
    if not hub_id:
        print("error: no hub id", file=sys.stderr)
        return 2
    zones = await client.get_hub_zones(hub_id)
    for zone in zones:
        print(f"{zone.ZoneId}\t{zone.ZoneName}\thub={zone.HubId}\tappliances={len(zone.Appliances)}")
        if args.verbose:
            for app in zone.Appliances:
                print(f"  {app.ApplianceId}\t{app.FriendlyName}\t{app.ApplianceModel or app.ApplianceType}")
    return 0


async def cmd_appliances(client: DimplexControl, args: argparse.Namespace) -> int:
    hubs = await client.get_hubs()
    for hub in hubs:
        if args.hub and hub.HubId != args.hub:
            continue
        zones = await client.get_hub_zones(hub.HubId)
        for zone in zones:
            for app in zone.Appliances:
                print(
                    f"{app.ApplianceId}\t{app.FriendlyName}\t"
                    f"{app.ApplianceModel or app.ApplianceType}\t"
                    f"zone={zone.ZoneName}\thub={hub.HubId}"
                )
    return 0


async def cmd_status(client: DimplexControl, args: argparse.Namespace) -> int:
    overview = await client.get_appliance_overview(args.hub, [args.appliance])
    if not overview:
        print("(no status — appliance offline or empty overview)")
        return 0
    status = overview[0]
    print(json.dumps(status.model_dump(mode="json"), indent=2, default=str))
    return 0


async def cmd_energy(client: DimplexControl, args: argparse.Namespace) -> int:
    report = await client.get_tsi_energy_report(hub_id=args.hub, days_back=args.days)
    summary: dict[str, Any] = {
        "hub_id": report.HubId,
        "appliances": {app_id: len(points or []) for app_id, points in (report.ApplianceTelemetryData or {}).items()},
    }
    print(json.dumps(summary, indent=2))
    return 0


async def cmd_boost(client: DimplexControl, args: argparse.Namespace) -> int:
    if not args.yes:
        print("error: control commands require --yes", file=sys.stderr)
        return 2
    await client.set_boost(
        args.hub,
        [args.appliance],
        temperature=args.temperature,
        duration_minutes=args.minutes,
        enable=not args.clear,
    )
    print("ok")
    return 0


async def cmd_away(client: DimplexControl, args: argparse.Namespace) -> int:
    if not args.yes:
        print("error: control commands require --yes", file=sys.stderr)
        return 2
    await client.set_away(
        args.hub,
        [args.appliance],
        temperature=args.temperature,
        enable=not args.clear,
    )
    print("ok")
    return 0


async def cmd_eco(client: DimplexControl, args: argparse.Namespace) -> int:
    if not args.yes:
        print("error: control commands require --yes", file=sys.stderr)
        return 2
    await client.set_eco_start(args.hub, [args.appliance], not args.clear)
    print("ok")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dimplex",
        description="Dimplex Control cloud CLI (debug / smoke tests)",
    )
    parser.add_argument(
        "--tokens-file",
        default=os.environ.get("DIMPLEX_TOKENS_FILE"),
        help="JSON token file (default: env DIMPLEX_TOKENS_FILE or DIMPLEX_* vars)",
    )
    parser.add_argument(
        "--show-tokens",
        action="store_true",
        help="Print full tokens (default: redacted)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_login = sub.add_parser("login", help="Validate tokens and print redacted status")
    p_login.set_defaults(func=cmd_login)

    p_hubs = sub.add_parser("hubs", help="List hubs")
    p_hubs.set_defaults(func=cmd_hubs)

    p_zones = sub.add_parser("zones", help="List zones for a hub")
    p_zones.add_argument("--hub", help="Hub id (default: first hub)")
    p_zones.add_argument("-v", "--verbose", action="store_true")
    p_zones.set_defaults(func=cmd_zones)

    p_apps = sub.add_parser("appliances", help="List appliances")
    p_apps.add_argument("--hub", help="Filter by hub id")
    p_apps.set_defaults(func=cmd_appliances)

    p_status = sub.add_parser("status", help="Appliance overview status")
    p_status.add_argument("hub")
    p_status.add_argument("appliance")
    p_status.set_defaults(func=cmd_status)

    p_energy = sub.add_parser("energy", help="Energy report summary (point counts only)")
    p_energy.add_argument("hub")
    p_energy.add_argument("--days", type=int, default=30)
    p_energy.set_defaults(func=cmd_energy)

    for name, help_text, defaults in (
        ("boost", "Enable or clear boost (--yes required)", {"minutes": 60, "temperature": 25.0}),
        ("away", "Enable or clear away (--yes required)", {"temperature": 16.0}),
        ("eco", "Enable or clear EcoStart (--yes required)", {}),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("hub")
        p.add_argument("appliance")
        p.add_argument("--yes", action="store_true", help="Confirm control write")
        p.add_argument("--clear", action="store_true", help="Disable the mode")
        if "temperature" in defaults:
            p.add_argument("--temperature", type=float, default=defaults["temperature"])
        if "minutes" in defaults:
            p.add_argument("--minutes", type=int, default=defaults["minutes"])
        p.set_defaults(func={"boost": cmd_boost, "away": cmd_away, "eco": cmd_eco}[name])

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    async def run(client: DimplexControl) -> int:
        func: Callable[..., Awaitable[int]] = args.func
        return await func(client, args)

    return asyncio.run(_with_client(args, run))


if __name__ == "__main__":
    raise SystemExit(main())
