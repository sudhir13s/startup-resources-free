"""Tiny CLI for inspecting the freellm catalog without writing Python.

Usage:
    python -m freellm catalog
    python -m freellm catalog --modality text
    python -m freellm plan --modality text --task-name extract-record
    python -m freellm quotas
    python -m freellm keys
    python -m freellm smoke --modality text
    python -m freellm version
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import asdict

from freellm import __version__, quotas
from freellm.errors import AllProvidersExhaustedError
from freellm.providers import PROVIDERS, list_providers
from freellm.router import call_text, plan
from freellm.schemas import ALL_MODALITIES, Modality


def _print(payload: object) -> None:
    print(json.dumps(payload, indent=2, default=str))


def cmd_catalog(args: argparse.Namespace) -> int:
    if args.modality:
        modality: Modality = args.modality
        rows = list_providers(modality)
        _print(
            {
                "modality": modality,
                "count": len(rows),
                "entries": [
                    {
                        "provider": r.provider,
                        "model": r.model,
                        "env_var": r.env_var,
                        "speed_tier": r.speed_tier,
                        "free_tier_kind": r.free_tier.kind,
                    }
                    for r in rows
                ],
            }
        )
        return 0

    summary = {modality: len(entries) for modality, entries in PROVIDERS.items()}
    _print({"total": sum(summary.values()), "by_modality": summary})
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    p = plan(modality=args.modality, task_name=args.task_name)
    _print(p.model_dump())
    return 0 if p.chosen else 2


def cmd_quotas(args: argparse.Namespace) -> int:
    state = quotas.load()
    out = {
        "quota_file": str(quotas._quota_path()),
        "entries": {key: asdict(val) for key, val in state.entries.items()},
    }
    _print(out)
    return 0


def cmd_version(args: argparse.Namespace) -> int:
    _print({"version": __version__})
    return 0


def cmd_keys(args: argparse.Namespace) -> int:
    """Show which env vars are set without leaking values."""
    rows = list_providers()
    seen_vars: set[str] = set()
    out: list[dict[str, str | bool]] = []
    for r in rows:
        if r.env_var in seen_vars:
            continue
        seen_vars.add(r.env_var)
        out.append({"env_var": r.env_var, "set": bool(os.environ.get(r.env_var))})
    _print(out)
    return 0


def cmd_smoke(args: argparse.Namespace) -> int:
    """Send a 1-token request through the chain for one modality.

    Skips cleanly (exit 0, explanatory message) when no provider key is
    set — this is expected in CI / a fresh clone, not a failure.
    """
    if args.modality != "text":
        _print({"modality": args.modality, "status": "skipped", "reason": "only text is live"})
        return 0

    p = plan(modality="text", task_name="cli-smoke")
    if p.chosen is None:
        _print(
            {
                "modality": "text",
                "status": "skipped",
                "reason": "no provider API key set — set one of the *_API_KEY / *_TOKEN "
                "env vars listed by `python -m freellm keys` to run a live smoke test",
            }
        )
        return 0

    async def _run() -> None:
        result = await call_text(
            messages=[{"role": "user", "content": "hi"}],
            task_name="cli-smoke",
            max_tokens=1,
        )
        _print(
            {
                "modality": "text",
                "status": "ok",
                "provider_used": result.provider_used,
                "model_used": result.model_used,
                "latency_ms": result.latency_ms,
            }
        )

    try:
        asyncio.run(_run())
    except AllProvidersExhaustedError as e:
        _print({"modality": "text", "status": "exhausted", "chain_attempted": e.chain_attempted})
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="freellm", description="Free-LLM router CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_catalog = sub.add_parser("catalog", help="Show catalog")
    p_catalog.add_argument("--modality", choices=ALL_MODALITIES, default=None)
    p_catalog.set_defaults(func=cmd_catalog)

    p_plan = sub.add_parser("plan", help="Show routing plan without making a call")
    p_plan.add_argument("--modality", choices=ALL_MODALITIES, required=True)
    p_plan.add_argument("--task-name", required=True)
    p_plan.set_defaults(func=cmd_plan)

    p_quotas = sub.add_parser("quotas", help="Show persisted quota counters")
    p_quotas.set_defaults(func=cmd_quotas)

    p_keys = sub.add_parser("keys", help="Show which provider env vars are set")
    p_keys.set_defaults(func=cmd_keys)

    p_version = sub.add_parser("version", help="Show freellm version")
    p_version.set_defaults(func=cmd_version)

    p_smoke = sub.add_parser(
        "smoke", help="Send a 1-token request through the chain (skips cleanly with no keys)"
    )
    p_smoke.add_argument("--modality", choices=ALL_MODALITIES, default="text")
    p_smoke.set_defaults(func=cmd_smoke)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
