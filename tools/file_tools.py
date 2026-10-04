import re
from tools.common import SOURCE_PATH

def read_source():
    return SOURCE_PATH.read_text(encoding="utf-8")

def set_interval(interval_ms):
    if type(interval_ms) is not int or not 100 <= interval_ms <= 2000:
        raise ValueError("interval_ms must be an integer between 100 and 2000")
    source = read_source()
    updated, count = re.subn(r"(?m)^#define LED_INTERVAL_MS \d+$",
                            f"#define LED_INTERVAL_MS {interval_ms}", source)
    if count != 1:
        raise ValueError("Expected exactly one LED_INTERVAL_MS definition")
    SOURCE_PATH.write_text(updated, encoding="utf-8")
    return {"success": True, "interval_ms": interval_ms}
