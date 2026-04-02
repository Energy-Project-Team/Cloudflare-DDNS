#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

APP_NAME = "cloudflare-ddns"
SERVICE_NAME = "cloudflare-ddns.service"
TIMER_NAME = "cloudflare-ddns.timer"
INSTALL_DIR = Path("/opt/cloudflare-ddns")
DEFAULT_ENV_PATH = INSTALL_DIR / ".env"

CF_API_BASE = "https://api.cloudflare.com/client/v4"
IPV4_URL = "https://api.ipify.org"
IPV6_URL = "https://api64.ipify.org"


@dataclass
class Target:
    name: str
    type: str
    token: str
    proxied: bool = False
    zone_id: str | None = None
    zone_name: str | None = None
    ip_mode: str | None = None


def configure_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def load_environment(env_path: str | None = None) -> Path | None:
    candidate = env_path or os.getenv("CF_DDNS_ENV")
    if candidate:
        path = Path(candidate)
        if path.exists():
            load_dotenv(path, override=True)
            return path
    if DEFAULT_ENV_PATH.exists():
        load_dotenv(DEFAULT_ENV_PATH, override=True)
        return DEFAULT_ENV_PATH
    local_env = Path(".env")
    if local_env.exists():
        load_dotenv(local_env, override=True)
        return local_env
    return None


def validate_ip_mode(value: str, *, field_name: str) -> str:
    mode = str(value).strip().lower()
    if mode not in {"ipv4", "ipv6"}:
        raise RuntimeError(f"{field_name} must be 'ipv4' or 'ipv6', got: {value}")
    return mode


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return bool(value)



def load_targets() -> list[Target]:
    raw_targets = os.getenv("CF_TARGETS_JSON", "").strip()
    targets_file = os.getenv("CF_TARGETS_FILE", "").strip()

    items: Any
    if targets_file:
        path = Path(targets_file)
        if not path.exists():
            raise RuntimeError(f"CF_TARGETS_FILE does not exist: {path}")
        try:
            items = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Failed to parse CF_TARGETS_FILE JSON: {exc}") from exc
    else:
        if not raw_targets:
            raise RuntimeError("Set CF_TARGETS_FILE or CF_TARGETS_JSON in .env")
        try:
            items = json.loads(raw_targets)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Failed to parse CF_TARGETS_JSON: {exc}") from exc

    if not isinstance(items, list) or not items:
        raise RuntimeError("Targets config must be a non-empty JSON array")

    targets: list[Target] = []
    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise RuntimeError(f"Target #{i} must be a JSON object")

        for key in ("name", "type", "token"):
            if not item.get(key):
                raise RuntimeError(f"Target #{i} missing required key: {key}")

        if not item.get("zone_id") and not item.get("zone_name"):
            raise RuntimeError(f"Target #{i} must have either zone_id or zone_name")

        record_type = str(item["type"]).strip().upper()
        if record_type not in {"A", "AAAA"}:
            raise RuntimeError(f"Target #{i} has invalid type: {record_type}")

        target_ip_mode = item.get("ip_mode")
        if target_ip_mode is not None:
            target_ip_mode = validate_ip_mode(target_ip_mode, field_name=f"Target #{i} ip_mode")

        targets.append(
            Target(
                name=str(item["name"]).strip(),
                type=record_type,
                token=str(item["token"]).strip(),
                proxied=parse_bool(item.get("proxied", False)),
                zone_id=str(item["zone_id"]).strip() if item.get("zone_id") else None,
                zone_name=str(item["zone_name"]).strip() if item.get("zone_name") else None,
                ip_mode=target_ip_mode,
            )
        )

    return targets


def get_global_ip_mode() -> str:
    return validate_ip_mode(os.getenv("IP_MODE", "ipv4"), field_name="IP_MODE")


def get_update_interval() -> int:
    raw = os.getenv("UPDATE_INTERVAL", "120").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError("UPDATE_INTERVAL must be an integer") from exc
    if value < 5:
        raise RuntimeError("UPDATE_INTERVAL must be >= 5 seconds")
    return value


def get_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def cf_request(
    method: str,
    path: str,
    token: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = requests.request(
        method=method,
        url=f"{CF_API_BASE}{path}",
        headers=get_headers(token),
        params=params,
        json=json_body,
        timeout=20,
    )
    response.raise_for_status()

    data = response.json()
    if not data.get("success", False):
        errors = data.get("errors", [])
        raise RuntimeError(f"Cloudflare API error: {errors}")

    return data


def detect_public_ip(ip_mode: str) -> str:
    url = IPV6_URL if ip_mode == "ipv6" else IPV4_URL
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    ip = response.text.strip()
    if not ip:
        raise RuntimeError("Public IP detection returned an empty response")
    return ip


def resolve_zone_id(target: Target) -> str:
    if target.zone_id:
        return target.zone_id

    data = cf_request(
        "GET",
        "/zones",
        target.token,
        params={"name": target.zone_name, "status": "active", "per_page": 1},
    )
    result = data.get("result", [])
    if not result:
        raise RuntimeError(f"Zone not found: {target.zone_name}")
    return str(result[0]["id"])


def resolve_record(target: Target, zone_id: str) -> dict[str, Any]:
    data = cf_request(
        "GET",
        f"/zones/{zone_id}/dns_records",
        target.token,
        params={"type": target.type, "name": target.name, "per_page": 1},
    )
    result = data.get("result", [])
    if not result:
        raise RuntimeError(f"DNS record not found: {target.type} {target.name}")
    return result[0]


def run_once(*, dry_run: bool = False, verbose_config: bool = False) -> int:
    env_path = load_environment()
    configure_logging()

    targets = load_targets()
    global_mode = get_global_ip_mode()
    interval = get_update_interval()

    logging.info("Loaded %d targets", len(targets))
    logging.info("Environment file: %s", env_path if env_path else "<not found>")
    logging.info("Global IP mode: %s", global_mode)
    logging.info("Update interval: %s seconds", interval)

    ip_cache: dict[str, str] = {}
    updated_count = 0

    for target in targets:
        effective_mode = target.ip_mode or global_mode
        expected_type = "A" if effective_mode == "ipv4" else "AAAA"
        if target.type != expected_type:
            logging.warning(
                "Skipping %s (%s): target type does not match effective ip_mode=%s",
                target.name,
                target.type,
                effective_mode,
            )
            continue

        if effective_mode not in ip_cache:
            ip_cache[effective_mode] = detect_public_ip(effective_mode)
            logging.info("Detected public %s: %s", effective_mode, ip_cache[effective_mode])

        current_ip = ip_cache[effective_mode]
        zone_id = resolve_zone_id(target)
        record = resolve_record(target, zone_id)
        old_ip = str(record.get("content", "")).strip()

        if verbose_config:
            logging.info(
                "Target=%s type=%s zone_id=%s proxied=%s ip_mode=%s",
                target.name,
                target.type,
                zone_id,
                target.proxied,
                effective_mode,
            )

        if old_ip == current_ip:
            logging.info("No change for %s %s: %s", target.type, target.name, current_ip)
            continue

        if dry_run:
            logging.info(
                "[DRY RUN] Would update %s %s: %s -> %s",
                target.type,
                target.name,
                old_ip or "<empty>",
                current_ip,
            )
            continue

        cf_request(
            "PUT",
            f"/zones/{zone_id}/dns_records/{record['id']}",
            target.token,
            json_body={
                "type": target.type,
                "name": target.name,
                "content": current_ip,
                "ttl": 1,
                "proxied": target.proxied,
            },
        )
        updated_count += 1
        logging.info(
            "Updated %s %s: %s -> %s (proxied=%s)",
            target.type,
            target.name,
            old_ip or "<empty>",
            current_ip,
            target.proxied,
        )

    logging.info("Done. Updated records: %d", updated_count)
    return 0


def run_forever() -> int:
    load_environment()
    configure_logging()
    interval = get_update_interval()
    logging.info("Starting daemon mode with interval=%s seconds", interval)

    while True:
        try:
            run_once()
        except Exception as exc:
            logging.exception("Run failed: %s", exc)
        time.sleep(interval)


def validate_config() -> int:
    env_path = load_environment()
    configure_logging()

    targets = load_targets()
    global_mode = get_global_ip_mode()
    interval = get_update_interval()

    logging.info("Environment file: %s", env_path if env_path else "<not found>")
    logging.info("Config is valid")
    logging.info("Targets: %d", len(targets))
    logging.info("Global IP mode: %s", global_mode)
    logging.info("Update interval: %d seconds", interval)

    for idx, target in enumerate(targets, start=1):
        logging.info(
            "Target #%d: name=%s type=%s zone=%s proxied=%s ip_mode=%s",
            idx,
            target.name,
            target.type,
            target.zone_id or target.zone_name,
            target.proxied,
            target.ip_mode or "<global>",
        )
    return 0


def show_config() -> int:
    env_path = load_environment()
    targets = load_targets()
    payload = {
        "env_path": str(env_path) if env_path else None,
        "ip_mode": get_global_ip_mode(),
        "update_interval": get_update_interval(),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "targets": [
            {
                "name": t.name,
                "type": t.type,
                "zone_id": t.zone_id,
                "zone_name": t.zone_name,
                "proxied": t.proxied,
                "ip_mode": t.ip_mode,
            }
            for t in targets
        ],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def test_token() -> int:
    load_environment()
    configure_logging()
    targets = load_targets()

    unique_tokens = list(dict.fromkeys(t.token for t in targets))
    logging.info("Testing %d unique token(s)", len(unique_tokens))

    failures = 0
    for idx, token in enumerate(unique_tokens, start=1):
        try:
            data = cf_request("GET", "/user/tokens/verify", token)
            result = data.get("result", {})
            logging.info(
                "Token #%d valid: status=%s id=%s",
                idx,
                result.get("status"),
                result.get("id"),
            )
        except Exception as exc:
            failures += 1
            logging.error("Token #%d failed validation: %s", idx, exc)

    return 1 if failures else 0


def list_zones() -> int:
    load_environment()
    configure_logging()
    targets = load_targets()

    seen_tokens: set[str] = set()
    for idx, target in enumerate(targets, start=1):
        if target.token in seen_tokens:
            continue
        seen_tokens.add(target.token)
        data = cf_request("GET", "/zones", target.token, params={"per_page": 50})
        logging.info("Token #%d zones:", idx)
        for zone in data.get("result", []):
            logging.info(" - %s (%s)", zone.get("name"), zone.get("id"))
    return 0


def check() -> int:
    return run_once(dry_run=True, verbose_config=True)


def call_systemctl(action: str) -> int:
    command = ["systemctl", action, SERVICE_NAME]
    print(" ".join(command))
    completed = subprocess.run(command, check=False)
    return completed.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cloudflare-ddns",
        description="Cloudflare DDNS updater with multi-target support and systemd helpers.",
    )
    parser.add_argument(
        "--env-file",
        dest="env_file",
        help="Path to .env file (default: /opt/cloudflare-ddns/.env or local .env)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("run", help="Run continuously using UPDATE_INTERVAL from .env")
    subparsers.add_parser("once", help="Run one update cycle")
    subparsers.add_parser("check", help="Show what would be updated without changing records")
    subparsers.add_parser("validate", help="Validate .env and target configuration")
    subparsers.add_parser("show-config", help="Print parsed configuration as JSON")
    subparsers.add_parser("list-zones", help="List Cloudflare zones available to configured tokens")
    subparsers.add_parser("test-token", help="Verify configured Cloudflare tokens")
    subparsers.add_parser("restart", help="Restart the systemd service")
    subparsers.add_parser("stop", help="Stop the systemd service")
    subparsers.add_parser("version", help="Show app version")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.env_file:
        os.environ["CF_DDNS_ENV"] = args.env_file

    command = args.command
    if command == "run":
        return run_forever()
    if command == "once":
        return run_once()
    if command == "check":
        return check()
    if command == "validate":
        return validate_config()
    if command == "show-config":
        return show_config()
    if command == "list-zones":
        return list_zones()
    if command == "test-token":
        return test_token()
    if command == "restart":
        return call_systemctl("restart")
    if command == "stop":
        return call_systemctl("stop")
    if command == "version":
        print("cloudflare-ddns 1.0.0")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
