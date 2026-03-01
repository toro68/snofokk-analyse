#!/usr/bin/env python3
"""Forny Netatmo refresh token og oppdater .env lokalt."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import requests


def _load_dotenv(env_path: Path) -> None:
    """Best effort loading av .env uten hard avhengighet."""
    try:
        from dotenv import load_dotenv  # type: ignore[import-not-found]

        if env_path.exists():
            load_dotenv(env_path)
    except Exception:
        # Scriptet skal fungere selv om python-dotenv ikke er installert.
        pass


def _get_required(name: str) -> str:
    value = (os.getenv(name) or "").strip().strip('"').strip("'")
    if not value:
        raise ValueError(f"Mangler {name}")
    return value


def _update_env_file(env_path: Path, key: str, value: str) -> None:
    """Oppdater eller legg til KEY=VALUE i .env, bevarer øvrige linjer."""
    line_out = f'{key}="{value}"\n'
    if not env_path.exists():
        env_path.write_text(line_out, encoding="utf-8")
        return

    content = env_path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    replaced = False
    new_lines: list[str] = []

    for line in lines:
        if pattern.match(line) and not replaced:
            new_lines.append(line_out)
            replaced = True
        else:
            new_lines.append(line)

    if not replaced:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] = new_lines[-1] + "\n"
        new_lines.append(line_out)

    env_path.write_text("".join(new_lines), encoding="utf-8")


def _mask(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:6]}...{value[-4:]}"


def rotate_token(timeout_seconds: int) -> dict:
    client_id = _get_required("NETATMO_CLIENT_ID")
    client_secret = _get_required("NETATMO_CLIENT_SECRET")
    refresh_token = _get_required("NETATMO_REFRESH_TOKEN")

    response = requests.post(
        "https://api.netatmo.com/oauth2/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=timeout_seconds,
    )

    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text}

    if response.status_code >= 400:
        raise RuntimeError(f"Netatmo token refresh feilet ({response.status_code}): {payload}")

    if not isinstance(payload, dict):
        raise RuntimeError("Uventet responsformat fra Netatmo")

    new_refresh = str(payload.get("refresh_token") or "").strip()
    new_access = str(payload.get("access_token") or "").strip()
    expires_in = payload.get("expires_in")

    if not new_refresh:
        raise RuntimeError(f"Fant ikke refresh_token i respons: {payload}")
    if not new_access:
        raise RuntimeError(f"Fant ikke access_token i respons: {payload}")

    return {
        "refresh_token": new_refresh,
        "access_token": new_access,
        "expires_in": expires_in,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Forny Netatmo refresh token og oppdater lokal .env."
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Sti til .env-fil som skal oppdateres (default: .env)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="HTTP timeout i sekunder (default: 15)",
    )
    parser.add_argument(
        "--no-write-env",
        action="store_true",
        help="Ikke skriv ny refresh token til .env, kun print resultat",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env_path = Path(args.env_file).expanduser().resolve()
    _load_dotenv(env_path)

    try:
        result = rotate_token(timeout_seconds=args.timeout)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    new_refresh = result["refresh_token"]
    new_access = result["access_token"]
    expires_in = result["expires_in"]

    print("Netatmo token refresh OK")
    print(f"- access_token:  { _mask(new_access) }")
    print(f"- refresh_token: {new_refresh}")
    print(f"- expires_in:    {expires_in}")

    if not args.no_write_env:
        _update_env_file(env_path, "NETATMO_REFRESH_TOKEN", new_refresh)
        print(f"- oppdatert:     {env_path}")

    print("")
    print("Oppdater Streamlit secret med ny verdi:")
    print(f'NETATMO_REFRESH_TOKEN="{new_refresh}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
