import importlib.util
from pathlib import Path


MODULE = Path(__file__).with_name("filaflow_hook.py")
spec = importlib.util.spec_from_file_location("filaflow_hook", MODULE)
hook = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(hook)


def test_missing_config_is_fail_open(tmp_path, monkeypatch):
    gcode = tmp_path / "print.gcode"
    gcode.write_text("G1 E1", encoding="utf-8")
    monkeypatch.setattr(hook, "CONFIG_FILE", tmp_path / "missing.json")
    monkeypatch.setattr(hook, "APP_DIR", tmp_path)
    monkeypatch.setattr(hook, "LOG_FILE", tmp_path / "hook.log")
    monkeypatch.setattr(hook.sys, "argv", [str(MODULE), str(gcode)])
    assert hook.main() == 0
    assert gcode.read_text(encoding="utf-8") == "G1 E1"


def test_prusaslicer_pp_file_is_retried(tmp_path, monkeypatch):
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    queued = outbox / "job.pp"
    queued.write_bytes(b"GCDE")
    queued.with_suffix(".pp.json").write_text(
        '{"idempotency_key":"job","filename":"print.bgcode","file":"job.pp"}',
        encoding="utf-8",
    )
    uploaded = []
    monkeypatch.setattr(hook, "OUTBOX", outbox)
    monkeypatch.setattr(hook, "APP_DIR", tmp_path)
    monkeypatch.setattr(hook, "LOG_FILE", tmp_path / "hook.log")
    monkeypatch.setattr(hook, "load_config", lambda: {"server_url": "http://example", "printer_id": "printer", "api_token": "token"})
    monkeypatch.setattr(hook, "upload_file", lambda config, path: uploaded.append(path))

    assert hook.retry_all() == 0
    assert uploaded == [queued]


def test_enqueue_uses_original_output_basename(tmp_path, monkeypatch):
    source = tmp_path / "temporary.pp"
    source.write_text("G1 E1", encoding="utf-8")
    outbox = tmp_path / "outbox"
    monkeypatch.setattr(hook, "OUTBOX", outbox)
    monkeypatch.setenv("SLIC3R_PP_OUTPUT_NAME", r"C:\Prints\example.gcode")

    queued = hook.enqueue(source)
    manifest = queued.with_suffix(".pp.json").read_text(encoding="utf-8")

    assert '"filename": "example.gcode"' in manifest
