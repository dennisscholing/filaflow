#!/usr/bin/env python3
"""Fail-open, multi-printer PrusaSlicer hook with a durable local outbox."""
from __future__ import annotations

import argparse
import contextlib
import http.client
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import uuid
from pathlib import Path


APP_DIR = Path(os.environ.get("FILAFLOW_CLIENT_DIR", Path.home() / ".filaflow"))
CONFIG_FILE = Path(os.environ.get("FILAFLOW_CONFIG", APP_DIR / "config.json"))
OUTBOX = APP_DIR / "outbox"
LOG_FILE = APP_DIR / "filaflow-hook.log"


def log(message: str) -> None:
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as stream:
            stream.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except OSError:
        pass


def atomic_save(config: dict, backup_legacy: bool = False) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if backup_legacy and CONFIG_FILE.exists():
        backup = CONFIG_FILE.with_name(f"config-v1-{time.strftime('%Y%m%d-%H%M%S')}.bak")
        shutil.copy2(CONFIG_FILE, backup)
        with contextlib.suppress(OSError): backup.chmod(0o600)
    temporary = CONFIG_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(config, indent=2), encoding="utf-8")
    temporary.replace(CONFIG_FILE)
    with contextlib.suppress(OSError): CONFIG_FILE.chmod(0o600)


def normalize_config(raw: dict, persist: bool = True) -> dict:
    if raw.get("version") == 2:
        config = raw
    elif {"server_url", "printer_id", "api_token"}.issubset(raw):
        printer_id = str(raw["printer_id"])
        config = {"version": 2, "server_url": str(raw["server_url"]).rstrip("/"), "default_printer_id": printer_id,
                  "printers": {printer_id: {"api_token": str(raw["api_token"]), "profiles": []}}}
        if persist: atomic_save(config, backup_legacy=True)
        log("Migrated single-printer client configuration to version 2")
    else:
        raise ValueError("Client configuration is incomplete")
    if not config.get("server_url") or not isinstance(config.get("printers"), dict):
        raise ValueError("Client configuration is incomplete")
    default = config.get("default_printer_id")
    if default and default not in config["printers"]:
        raise ValueError("Default printer is not configured")
    owners: dict[str, str] = {}
    for printer_id, item in config["printers"].items():
        if not item.get("api_token") or not isinstance(item.get("profiles", []), list):
            raise ValueError(f"Printer configuration is incomplete: {printer_id}")
        profiles = list(dict.fromkeys(profile.strip() for profile in item["profiles"] if profile.strip()))
        item["profiles"] = profiles
        for profile in profiles:
            key = profile.casefold()
            if key in owners and owners[key] != printer_id:
                raise ValueError(f'Profile "{profile}" is mapped to more than one printer')
            owners[key] = printer_id
    return config


def load_config() -> dict:
    return normalize_config(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))


def profile_owner(config: dict, profile: str) -> str | None:
    key = profile.strip().casefold()
    for printer_id, item in config["printers"].items():
        if any(candidate.casefold() == key for candidate in item.get("profiles", [])):
            return printer_id
    return None


def resolve_route(config: dict) -> dict:
    physical = os.environ.get("SLIC3R_PHYSICAL_PRINTER_SETTINGS_ID", "").strip()
    printer_profile = os.environ.get("SLIC3R_PRINTER_SETTINGS_ID", "").strip()
    for profile, mode in ((physical, "physical_profile"), (printer_profile, "printer_profile")):
        owner = profile_owner(config, profile) if profile else None
        if owner:
            return {"printer_id": owner, "source_profile": profile, "physical_profile": physical, "routing_mode": mode}
    default = config.get("default_printer_id")
    if not default:
        raise ValueError(f"No mapping exists for PrusaSlicer profile: {physical or printer_profile or '(not provided)'}")
    return {"printer_id": default, "source_profile": physical or printer_profile, "physical_profile": physical, "routing_mode": "default"}


def enqueue(source: Path, route: dict | None = None) -> Path:
    OUTBOX.mkdir(parents=True, exist_ok=True)
    job_id = str(uuid.uuid4())
    suffix = source.suffix or ".gcode"
    target = OUTBOX / f"{job_id}{suffix}"
    shutil.copy2(source, target)
    output_name = os.environ.get("SLIC3R_PP_OUTPUT_NAME") or source.name
    output_name = output_name.replace("\\", "/").rsplit("/", 1)[-1]
    manifest = {"idempotency_key": job_id, "filename": output_name, "file": target.name, "created_at": time.time(), **(route or {})}
    manifest_path = target.with_suffix(target.suffix + ".json")
    temporary = manifest_path.with_name(f"{manifest_path.name}.tmp")
    try:
        temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        temporary.replace(manifest_path)
    except Exception:
        target.unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)
        raise
    return target


def manifest_route(config: dict, manifest: dict) -> dict:
    printer_id = manifest.get("printer_id") or config.get("default_printer_id")
    if not printer_id or printer_id not in config["printers"]:
        raise ValueError("The queued job's printer is no longer configured")
    return {"printer_id": printer_id, "api_token": config["printers"][printer_id]["api_token"],
            "source_profile": manifest.get("source_profile", ""), "physical_profile": manifest.get("physical_profile", ""),
            "routing_mode": manifest.get("routing_mode", "legacy" if "printer_id" not in manifest else "profile")}


def upload_file(config: dict, path: Path) -> None:
    manifest_path = path.with_suffix(path.suffix + ".json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    route = manifest_route(config, manifest)
    parsed = urllib.parse.urlparse(config["server_url"].rstrip("/") + "/api/slicer/jobs")
    boundary = f"----FilaFlow{uuid.uuid4().hex}"
    fields = {"printer_id": route["printer_id"], "source_profile": route["source_profile"],
              "physical_profile": route["physical_profile"], "routing_mode": route["routing_mode"]}
    preamble = bytearray()
    for name, value in fields.items():
        preamble.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    preamble.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{manifest['filename']}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode())
    ending = f"\r\n--{boundary}--\r\n".encode()
    connection_class = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    connection = connection_class(parsed.hostname, parsed.port, timeout=45)
    endpoint = parsed.path or "/api/slicer/jobs"
    connection.putrequest("POST", endpoint)
    connection.putheader("Authorization", f"Bearer {route['api_token']}")
    connection.putheader("Idempotency-Key", manifest["idempotency_key"])
    connection.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
    connection.putheader("Content-Length", str(len(preamble) + path.stat().st_size + len(ending)))
    connection.endheaders(); connection.send(preamble)
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024): connection.send(chunk)
    connection.send(ending)
    response = connection.getresponse(); body = response.read(4096); connection.close()
    if response.status not in (200, 201):
        raise RuntimeError(f"Server returned {response.status}: {body.decode(errors='replace')}")
    path.unlink(missing_ok=True); manifest_path.unlink(missing_ok=True)


def retry_all() -> int:
    config = load_config(); failed = 0
    for manifest_path in sorted(OUTBOX.glob("*.json")):
        path = manifest_path.with_suffix("")
        if not path.is_file(): log(f"Missing outbox file for {manifest_path.name}"); failed += 1; continue
        try: upload_file(config, path); log(f"Uploaded: {path.name}")
        except Exception as error: failed += 1; log(f"Upload failed for {path.name}: {error}")
    return failed


def detach_upload() -> None:
    command = [sys.executable, str(Path(__file__).resolve()), "--retry"]
    kwargs = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "close_fds": True}
    if os.name == "nt": kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else: kwargs["start_new_session"] = True
    subprocess.Popen(command, **kwargs)


def empty_config(server_url: str) -> dict:
    return {"version": 2, "server_url": server_url.rstrip("/"), "default_printer_id": None, "printers": {}}


def add_printer(server_url: str, printer_id: str, token: str, profile: str = "", make_default: bool = False) -> None:
    config = load_config() if CONFIG_FILE.exists() else empty_config(server_url)
    config["server_url"] = server_url.rstrip("/")
    profile = profile.strip()
    owner = profile_owner(config, profile) if profile else None
    if owner and owner != printer_id: raise ValueError(f'Profile "{profile}" is already mapped to another printer')
    item = config["printers"].setdefault(printer_id, {"api_token": token, "profiles": []})
    item["api_token"] = token
    if profile and profile not in item["profiles"]: item["profiles"].append(profile)
    if make_default or not config.get("default_printer_id"): config["default_printer_id"] = printer_id
    atomic_save(config); log(f"Configured printer {printer_id}")


def add_profile(printer_id: str, profile: str) -> None:
    config = load_config()
    if printer_id not in config["printers"]: raise ValueError("Printer is not configured")
    profile = profile.strip()
    if not profile: raise ValueError("Profile name cannot be empty")
    owner = profile_owner(config, profile)
    if owner and owner != printer_id: raise ValueError(f'Profile "{profile}" is already mapped to another printer')
    if profile not in config["printers"][printer_id]["profiles"]: config["printers"][printer_id]["profiles"].append(profile)
    atomic_save(config)


def set_default(printer_id: str) -> None:
    config = load_config()
    if printer_id not in config["printers"]: raise ValueError("Printer is not configured")
    config["default_printer_id"] = printer_id; atomic_save(config)


def remove_printer(printer_id: str) -> None:
    config = load_config()
    if printer_id not in config["printers"]: raise ValueError("Printer is not configured")
    del config["printers"][printer_id]
    if config.get("default_printer_id") == printer_id: config["default_printer_id"] = next(iter(config["printers"]), None)
    atomic_save(config)


def show_printers() -> None:
    config = load_config()
    for printer_id, item in config["printers"].items():
        marker = " (default)" if printer_id == config.get("default_printer_id") else ""
        print(f"{printer_id}{marker}")
        for profile in item["profiles"]: print(f"  - {profile}")


def main() -> int:
    parser = argparse.ArgumentParser(description="FilaFlow multi-printer PrusaSlicer outbox")
    parser.add_argument("gcode", nargs="?")
    parser.add_argument("--retry", action="store_true")
    parser.add_argument("--configure", nargs=3, metavar=("URL", "PRINTER_ID", "TOKEN"))
    parser.add_argument("--add-printer", nargs=4, metavar=("URL", "PRINTER_ID", "TOKEN", "PROFILE"))
    parser.add_argument("--default", action="store_true")
    parser.add_argument("--add-profile", nargs=2, metavar=("PRINTER_ID", "PROFILE"))
    parser.add_argument("--set-default", metavar="PRINTER_ID")
    parser.add_argument("--remove-printer", metavar="PRINTER_ID")
    parser.add_argument("--list-printers", action="store_true")
    args = parser.parse_args()
    try:
        if args.configure: add_printer(*args.configure, make_default=True); return 0
        if args.add_printer: add_printer(*args.add_printer, make_default=args.default); return 0
        if args.add_profile: add_profile(*args.add_profile); return 0
        if args.set_default: set_default(args.set_default); return 0
        if args.remove_printer: remove_printer(args.remove_printer); return 0
        if args.list_printers: show_printers(); return 0
        if args.retry: return 1 if retry_all() else 0
        if not args.gcode: parser.print_help(); return 0
        source = Path(args.gcode)
        if not source.is_file(): raise FileNotFoundError(source)
        config = load_config(); route = resolve_route(config); queued = enqueue(source, route)
        log(f"Queued: {queued.name} -> {route['printer_id']} ({route['routing_mode']})"); detach_upload(); return 0
    except Exception as error:
        log(f"Hook warning: {error}")
        if args.gcode:
            print(f"FilaFlow warning: {error}", file=sys.stderr)
            return 0
        print(f"FilaFlow configuration error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
