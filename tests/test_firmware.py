import pytest
from tools.verify_tool import verify

def sample(interval=500, count=21):
    return f"BOOT_OK interval_ms={interval} gpio=4\n" + "\n".join(
        f"LED_{'ON' if i % 2 == 0 else 'OFF'} timestamp={i * interval}" for i in range(count))

def test_valid_log():
    assert verify(sample(), 500)["success"]

@pytest.mark.parametrize("text", ["", "LED_ON\nLED_OFF", sample(100), sample(count=2),
    sample().replace("LED_OFF", "LED_ON"), sample().replace("timestamp=1000", "timestamp=100"),
    sample() + "\nLED_ON timestamp=broken", sample() + "\nBOOT_OK interval_ms=500 gpio=4"])
def test_bad_logs_fail(text):
    assert not verify(text, 500)["success"]

def test_missing_boot_fails():
    assert not verify(sample().split("\n", 1)[1], 500)["success"]

def test_tolerance_boundary():
    text = sample().replace("timestamp=500\n", "timestamp=550\n")
    assert verify(text, 500, tolerance_ms=50)["success"]
    assert not verify(text, 500, tolerance_ms=49)["success"]
