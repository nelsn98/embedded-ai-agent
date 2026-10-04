import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIRMWARE_DIR = PROJECT_ROOT / "firmware"
SOURCE_PATH = FIRMWARE_DIR / "main" / "hello_world_main.c"

def run_idf(arguments, timeout):
    idf_root = os.environ.get("IDF_PATH")
    if not idf_root:
        return {"success": False, "return_code": None, "stdout": "",
                "stderr": "IDF_PATH missing. Open the ESP-IDF terminal first."}
    script = Path(idf_root) / "tools" / "idf.py"
    if not script.is_file():
        return {"success": False, "return_code": None, "stdout": "",
                "stderr": "IDF_PATH does not contain tools/idf.py"}
    command = [sys.executable, str(script), *arguments]
    try:
        result = subprocess.run(command, cwd=FIRMWARE_DIR, shell=False,
                                capture_output=True, text=True, errors="replace",
                                timeout=timeout)
        return {"success": result.returncode == 0, "return_code": result.returncode,
                "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.TimeoutExpired as exc:
        def decode(value):
            return value.decode(errors="replace") if isinstance(value, bytes) else (value or "")
        return {"success": False, "return_code": None, "stdout": decode(exc.stdout),
                "stderr": "ESP-IDF command timed out. " + decode(exc.stderr)}
    except OSError as exc:
        return {"success": False, "return_code": None, "stdout": "", "stderr": str(exc)}
