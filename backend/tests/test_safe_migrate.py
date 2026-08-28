import hashlib
import subprocess

import pytest
from sqlalchemy import create_engine, text

import migrate as migration


def test_unknown_database_revision_is_rejected(tmp_path):
    database = create_engine(f"sqlite+pysqlite:///{tmp_path / 'unknown.db'}")
    with database.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(text("INSERT INTO alembic_version VALUES ('unknown_revision')"))
    script = migration.ScriptDirectory.from_config(migration.alembic_config())
    with database.connect() as connection, pytest.raises(RuntimeError, match="unknown schema revision"):
        migration.revisions(connection, script)


def test_invalid_dump_is_never_published(tmp_path, monkeypatch):
    monkeypatch.setattr(migration.settings, "backup_dir", tmp_path)

    def invalid_run(command, **_kwargs):
        if command[0] == "pg_dump":
            output = next(item.removeprefix("--file=") for item in command if item.startswith("--file="))
            migration.Path(output).write_bytes(b"not a postgres dump")
            return
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(migration.subprocess, "run", invalid_run)
    with pytest.raises(subprocess.CalledProcessError):
        migration.verified_backup("0002_indx_t1_t8", "0003_printer_location")
    assert list((tmp_path / "pre-upgrade").iterdir()) == []


def test_verified_dump_and_checksum_are_published_atomically(tmp_path, monkeypatch):
    monkeypatch.setattr(migration.settings, "backup_dir", tmp_path)
    payload = b"representative custom dump"

    def valid_run(command, **_kwargs):
        if command[0] == "pg_dump":
            output = next(item.removeprefix("--file=") for item in command if item.startswith("--file="))
            migration.Path(output).write_bytes(payload)

    monkeypatch.setattr(migration.subprocess, "run", valid_run)
    dump = migration.verified_backup("0002_indx_t1_t8", "0003_printer_location")
    manifest = migration.json.loads(dump.with_suffix(".json").read_text(encoding="utf-8"))
    assert dump.read_bytes() == payload
    assert manifest["sha256"] == hashlib.sha256(payload).hexdigest()
    assert manifest["sourceRevision"] == "0002_indx_t1_t8"
    assert not list(dump.parent.glob("*.tmp"))
