import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.common import PROJECT_ROOT
from tools.build_tool import build
from tools.flash_tool import flash
from tools.monitor_tool import capture_log
from tools.verify_tool import verify


def run_pipeline(port, expected_ms, duration=20, tolerance_ms=50):
    report = {"success": False, "expected_ms": expected_ms, "port": port, "stages": {}}
    for name, action in [("build", build), ("flash", lambda: flash(port)),
                         ("monitor", lambda: capture_log(port, duration))]:
        print(name.upper(), flush=True)
        result = action()
        report["stages"][name] = result
        if not result["success"]:
            report["failed_stage"] = name
            return report
    result = verify(report["stages"]["monitor"]["log"], expected_ms, tolerance_ms)
    report["stages"]["verify"] = result
    report["success"] = result["success"]
    if not result["success"]:
        report["failed_stage"] = "verify"
    return report


def main():
    parser = argparse.ArgumentParser(description="Build, flash and verify a real ESP32")
    parser.add_argument("--port", required=True)
    parser.add_argument("--expected-ms", type=int, required=True)
    parser.add_argument("--duration", type=float, default=20)
    parser.add_argument("--tolerance-ms", type=int, default=50)
    args = parser.parse_args()
    if not 100 <= args.expected_ms <= 2000 or args.duration <= 0 or args.tolerance_ms < 0:
        parser.error("Expected 100..2000 ms, duration > 0, tolerance >= 0")
    report = run_pipeline(args.port, args.expected_ms, args.duration, args.tolerance_ms)
    output = PROJECT_ROOT / "reports" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output.mkdir(parents=True)
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (output / "device.log").write_text(report["stages"].get("monitor", {}).get("log", ""), encoding="utf-8")
    (output / "raw_device.log").write_text(report["stages"].get("monitor", {}).get("raw_log", ""), encoding="utf-8")
    print("PASS" if report["success"] else "FAIL: " + report.get("failed_stage", "unknown"))
    print("Report:", output / "report.json")
    if not report["success"]:
        print(json.dumps(report["stages"].get(report.get("failed_stage")), indent=2))
    return 0 if report["success"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
