import importlib.util
import json
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


def configure_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(hook, "APP_DIR", tmp_path)
    monkeypatch.setattr(hook, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(hook, "OUTBOX", tmp_path / "outbox")
    monkeypatch.setattr(hook, "LOG_FILE", tmp_path / "hook.log")


def test_version_one_config_is_backed_up_and_migrated(tmp_path, monkeypatch):
    configure_paths(tmp_path, monkeypatch)
    hook.CONFIG_FILE.write_text(json.dumps({"server_url": "http://nas:9000", "printer_id": "printer-a", "api_token": "token-a"}), encoding="utf-8")

    config = hook.load_config()

    assert config["version"] == 2
    assert config["default_printer_id"] == "printer-a"
    assert config["printers"]["printer-a"]["api_token"] == "token-a"
    assert list(tmp_path.glob("config-v1-*.bak"))


def test_physical_profile_wins_and_default_is_safe_fallback(tmp_path, monkeypatch):
    configure_paths(tmp_path, monkeypatch)
    config = {"version": 2, "server_url": "http://nas:9000", "default_printer_id": "default",
              "printers": {"default": {"api_token": "d", "profiles": []}, "physical": {"api_token": "p", "profiles": ["Workshop MK4"]}, "preset": {"api_token": "s", "profiles": ["MK4 preset"]}}}
    monkeypatch.setenv("SLIC3R_PHYSICAL_PRINTER_SETTINGS_ID", "Workshop MK4")
    monkeypatch.setenv("SLIC3R_PRINTER_SETTINGS_ID", "MK4 preset")
    assert hook.resolve_route(config)["printer_id"] == "physical"
    monkeypatch.setenv("SLIC3R_PHYSICAL_PRINTER_SETTINGS_ID", "Unknown physical")
    monkeypatch.setenv("SLIC3R_PRINTER_SETTINGS_ID", "Unknown preset")
    route = hook.resolve_route(config)
    assert route["printer_id"] == "default"
    assert route["routing_mode"] == "default"


def test_queued_job_keeps_original_printer_after_profile_changes(tmp_path, monkeypatch):
    configure_paths(tmp_path, monkeypatch)
    source = tmp_path / "print.gcode"
    source.write_text("G1 E1", encoding="utf-8")
    queued = hook.enqueue(source, {"printer_id": "printer-a", "source_profile": "Profile A", "physical_profile": "", "routing_mode": "printer_profile"})
    manifest = json.loads(queued.with_suffix(".gcode.json").read_text(encoding="utf-8"))
    config = {"version": 2, "server_url": "http://nas:9000", "default_printer_id": "printer-b",
              "printers": {"printer-a": {"api_token": "new-token-a", "profiles": []}, "printer-b": {"api_token": "token-b", "profiles": ["Profile A"]}}}
    route = hook.manifest_route(config, manifest)
    assert route["printer_id"] == "printer-a"
    assert route["api_token"] == "new-token-a"


def test_profile_cannot_be_claimed_by_two_printers(tmp_path, monkeypatch):
    configure_paths(tmp_path, monkeypatch)
    hook.add_printer("http://nas:9000", "printer-a", "token-a", "Shared profile")
    try:
        hook.add_printer("http://nas:9000", "printer-b", "token-b", "Shared profile")
    except ValueError as error:
        assert "already mapped" in str(error)
    else:
        raise AssertionError("Expected duplicate profile mapping to fail")
