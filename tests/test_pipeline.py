from pipeline import run_pipeline as module
from tests.test_firmware import sample


def test_pipeline_success(monkeypatch):
    monkeypatch.setattr(module, "build", lambda: {"success": True})
    monkeypatch.setattr(module, "flash", lambda port: {"success": True})
    monkeypatch.setattr(module, "capture_log", lambda port, duration: {"success": True, "log": sample()})
    assert module.run_pipeline("COM_TEST", 500)["success"]


def test_build_failure_stops_flash(monkeypatch):
    monkeypatch.setattr(module, "build", lambda: {"success": False})
    def forbidden(port):
        raise AssertionError("Flash must not run after build failure")
    monkeypatch.setattr(module, "flash", forbidden)
    assert module.run_pipeline("COM_TEST", 500)["failed_stage"] == "build"


def test_disconnect_stops_verification(monkeypatch):
    monkeypatch.setattr(module, "build", lambda: {"success": True})
    monkeypatch.setattr(module, "flash", lambda port: {"success": True})
    monkeypatch.setattr(module, "capture_log", lambda port, duration: {"success": False, "log": "", "error": "disconnected"})
    result = module.run_pipeline("COM_TEST", 500)
    assert not result["success"] and result["failed_stage"] == "monitor"
