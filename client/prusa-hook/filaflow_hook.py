#!/usr/bin/env python3
"""Fail-open PrusaSlicer hook with a durable local outbox.

PrusaSlicer invokes this script with the temporary G-code path as its final
argument. The hook only copies to an outbox and starts a detached uploader; it
never edits G-code and always exits successfully so printer delivery continues.
"""
from __future__ import annotations

import argparse
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
        # Logging is diagnostic only and may never break PrusaSlicer or retry.
        pass


def load_config() -> dict:
    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    required = {"server_url", "printer_id", "api_token"}
    missing = required - set(config)
    if missing:
        raise ValueError(f"Ontbrekende configuratie: {', '.join(sorted(missing))}")
    return config


def enqueue(source: Path) -> Path:
    OUTBOX.mkdir(parents=True, exist_ok=True)
    job_id = str(uuid.uuid4())
    suffix = source.suffix or ".gcode"
    target = OUTBOX / f"{job_id}{suffix}"
    shutil.copy2(source, target)
    output_name = os.environ.get("SLIC3R_PP_OUTPUT_NAME") or source.name
    # PrusaSlicer can provide an absolute Windows path here. Only send the
    # original basename so the API retains the real .gcode/.bgcode extension.
    output_name = output_name.replace("\\", "/").rsplit("/", 1)[-1]
    manifest = {"idempotency_key": job_id, "filename": output_name, "file": target.name, "created_at": time.time()}
    target.with_suffix(target.suffix + ".json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return target


def upload_file(config: dict, path: Path) -> None:
    manifest_path = path.with_suffix(path.suffix + ".json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    parsed = urllib.parse.urlparse(config["server_url"].rstrip("/") + "/api/slicer/jobs")
    boundary = f"----FilaFlow{uuid.uuid4().hex}"
    fields = {"printer_id": config["printer_id"]}
    preamble = bytearray()
    for name, value in fields.items():
        preamble.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    preamble.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{manifest['filename']}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode())
    ending = f"\r\n--{boundary}--\r\n".encode()
    connection_class = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    connection = connection_class(parsed.hostname, parsed.port, timeout=45)
    endpoint = parsed.path or "/api/slicer/jobs"
    connection.putrequest("POST", endpoint)
    connection.putheader("Authorization", f"Bearer {config['api_token']}")
    connection.putheader("Idempotency-Key", manifest["idempotency_key"])
    connection.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
    connection.putheader("Content-Length", str(len(preamble) + path.stat().st_size + len(ending)))
    connection.endheaders()
    connection.send(preamble)
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            connection.send(chunk)
    connection.send(ending)
    response = connection.getresponse()
    body = response.read(4096)
    connection.close()
    if response.status not in (200, 201):
        raise RuntimeError(f"Server antwoordde {response.status}: {body.decode(errors='replace')}")
    path.unlink(missing_ok=True)
    manifest_path.unlink(missing_ok=True)


def retry_all() -> int:
    config = load_config()
    failed = 0
    for manifest_path in sorted(OUTBOX.glob("*.json")):
        path = manifest_path.with_suffix("")
        if not path.is_file():
            log(f"Outboxbestand ontbreekt voor {manifest_path.name}")
            failed += 1
            continue
        try:
            upload_file(config, path)
            log(f"Geüpload: {path.name}")
        except Exception as error:
            failed += 1
            log(f"Upload mislukt voor {path.name}: {error}")
    return failed


def detach_upload() -> None:
    command = [sys.executable, str(Path(__file__).resolve()), "--retry"]
    kwargs = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "close_fds": True}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(command, **kwargs)


def configure(server_url: str, printer_id: str, api_token: str) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps({"server_url": server_url.rstrip("/"), "printer_id": printer_id, "api_token": api_token}, indent=2), encoding="utf-8")
    log("Clientconfiguratie opgeslagen")


def main() -> int:
    parser = argparse.ArgumentParser(description="FilaFlow PrusaSlicer outbox")
    parser.add_argument("gcode", nargs="?")
    parser.add_argument("--retry", action="store_true")
    parser.add_argument("--configure", nargs=3, metavar=("URL", "PRINTER_ID", "TOKEN"))
    args = parser.parse_args()
    if args.configure:
        configure(*args.configure); return 0
    if args.retry:
        return 1 if retry_all() else 0
    if not args.gcode:
        parser.print_help(); return 0
    try:
        source = Path(args.gcode)
        if not source.is_file(): raise FileNotFoundError(source)
        load_config()
        queued = enqueue(source)
        log(f"In outbox geplaatst: {queued.name}")
        detach_upload()
    except Exception as error:
        # Deliberately fail open: PrusaSlicer must continue to the printer.
        log(f"Hookwaarschuwing: {error}")
        print(f"FilaFlow-waarschuwing: {error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
