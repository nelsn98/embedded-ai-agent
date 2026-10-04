import re

EVENT = re.compile(r"^LED_(ON|OFF) timestamp=(\d+)$")
BOOT = re.compile(r"^BOOT_OK interval_ms=(\d+) gpio=(\d+)$")

def verify(log_text, expected_ms, tolerance_ms=50, min_cycles=10):
    if expected_ms <= 0 or tolerance_ms < 0 or min_cycles < 1:
        raise ValueError("Invalid verification parameters")
    lines = [line.strip() for line in log_text.splitlines()]
    boots = [BOOT.fullmatch(line) for line in lines if BOOT.fullmatch(line)]
    events = [(match[1], int(match[2])) for line in lines
              if (match := EVENT.fullmatch(line))]
    deltas = [b[1] - a[1] for a, b in zip(events, events[1:])]
    checks = {
        "boot": len(boots) == 1 and int(boots[0][1]) == expected_ms,
        "led_on": any(state == "ON" for state, _ in events),
        "led_off": any(state == "OFF" for state, _ in events),
        "enough_cycles": len(deltas) >= min_cycles * 2,
        "alternating": bool(deltas) and all(a[0] != b[0] for a, b in zip(events, events[1:])),
        "interval": bool(deltas) and all(delta > 0 and abs(delta - expected_ms) <= tolerance_ms for delta in deltas),
        "valid_events": not any(line.startswith("LED_") and not EVENT.fullmatch(line) for line in lines),
    }
    return {"success": all(checks.values()), "checks": checks,
            "expected_ms": expected_ms, "tolerance_ms": tolerance_ms,
            "event_count": len(events), "intervals_ms": deltas,
            "verification_scope": "UART software behavior; electrical and optical output unmeasured"}
