"""Guarded database migration entrypoint for production containers."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.config import settings
from app.database import engine


LOCK_ID = 0x46494C41464C4F57
FAILURE_FILE = settings.config_dir / "migration-failed.json"
MIGRATION_STATE: dict[str, str | None] = {"source": None, "target": None}


def alembic_config() -> Config:
    config = Config(str(Path(__file__).with_name("alembic.ini")))
    config.set_main_option("script_location", str(Path(__file__).with_name("alembic")))
    return config


def revisions(connection, script: ScriptDirectory) -> tuple[tuple[str, ...], str]:
    current = tuple(MigrationContext.configure(connection).get_current_heads())
    heads = script.get_heads()
    if len(heads) != 1:
        raise RuntimeError(f"Expected one schema head, found {heads}")
    known = {revision.revision for revision in script.walk_revisions()}
    unknown = [revision for revision in current if revision not in known]
    if unknown:
        raise RuntimeError(f"Database has an unknown schema revision: {', '.join(unknown)}")
    if len(current) > 1:
        raise RuntimeError(f"Database has divergent schema revisions: {', '.join(current)}")
    return current, heads[0]


def database_environment() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PGHOST": settings.database_host,
            "PGPORT": str(settings.database_port),
            "PGDATABASE": settings.database_name,
            "PGUSER": settings.database_user,
            "PGPASSWORD": settings.database_password,
        }
    )
    return env


def verified_backup(source: str, target: str) -> Path:
    directory = settings.backup_dir / "pre-upgrade"
    directory.mkdir(parents=True, exist_ok=True)
    if not os.access(directory, os.W_OK):
        raise RuntimeError(f"Pre-upgrade backup directory is not writable: {directory}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    base = f"filaflow-{stamp}-{source or 'empty'}-to-{target}"
    temporary = directory / f".{base}.dump.tmp"
    final = directory / f"{base}.dump"
    try:
        subprocess.run(["pg_dump", "--format=custom", "--compress=9", f"--file={temporary}"], env=database_environment(), check=True, timeout=1800)
        subprocess.run(["pg_restore", "--list", str(temporary)], check=True, stdout=subprocess.DEVNULL, timeout=120)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    checksum = hashlib.sha256()
    with temporary.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            checksum.update(chunk)
    digest = checksum.hexdigest()
    temporary.replace(final)
    manifest = {"createdAt": datetime.now(timezone.utc).isoformat(), "sourceRevision": source or None, "targetRevision": target, "sha256": digest, "dump": final.name}
    manifest_path = final.with_suffix(".json")
    manifest_temporary = manifest_path.with_suffix(".json.tmp")
    manifest_temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest_temporary.replace(manifest_path)
    backups = sorted(directory.glob("filaflow-*.dump"), key=lambda path: path.stat().st_mtime, reverse=True)
    for old in backups[max(1, settings.preupgrade_backup_keep):]:
        old.unlink(missing_ok=True)
        old.with_suffix(".json").unlink(missing_ok=True)
    return final


def write_failure(error: Exception, source: str | None, target: str | None) -> None:
    settings.config_dir.mkdir(parents=True, exist_ok=True)
    payload = {"failedAt": datetime.now(timezone.utc).isoformat(), "sourceRevision": source, "targetRevision": target, "error": str(error)}
    temporary = FAILURE_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(FAILURE_FILE)


def migrate() -> None:
    config = alembic_config()
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    MIGRATION_STATE["target"] = heads[0] if len(heads) == 1 else None
    with engine.connect() as lock_connection:
        if engine.dialect.name == "postgresql":
            lock_connection.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": LOCK_ID})
        current, target = revisions(lock_connection, script)
        source = current[0] if current else None
        MIGRATION_STATE.update(source=source, target=target)
        if current == (target,):
            FAILURE_FILE.unlink(missing_ok=True)
            print(f"Database schema is current at {target}")
            return
        if FAILURE_FILE.exists():
            raise RuntimeError(f"A previous migration failed. Follow the recovery guide before removing {FAILURE_FILE}")
        if not settings.migrations_enabled:
            raise RuntimeError("Database migration required, but the safe migration gate is disabled. Update docker-compose.yml before starting this image.")
        backup = verified_backup(source or "", target)
        print(f"Verified pre-upgrade backup: {backup}")
        command.upgrade(config, target)
        with engine.connect() as verify_connection:
            upgraded, _ = revisions(verify_connection, script)
        if upgraded != (target,):
            raise RuntimeError(f"Migration verification failed: expected {target}, found {upgraded}")
        FAILURE_FILE.unlink(missing_ok=True)
        print(f"Database upgraded from {source or 'empty'} to {target}")


if __name__ == "__main__":
    try:
        migrate()
    except Exception as exc:
        try:
            write_failure(exc, MIGRATION_STATE["source"], MIGRATION_STATE["target"])
        except Exception:
            pass
        print(f"Safe migration gate stopped startup: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
