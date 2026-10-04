import serial
from tools import monitor_tool as module
from tools.verify_tool import verify


def run_capture(monkeypatch, chunks):
    clock = [0.0]
    def monotonic():
        clock[0] += 0.1
        return clock[0]
    class Device:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def reset_input_buffer(self):
            pass
        def readline(self):
            return chunks.pop(0) if chunks else b''
    monkeypatch.setattr(serial, 'Serial', lambda *args, **kwargs: Device())
    monkeypatch.setattr(module.time, 'monotonic', monotonic)
    monkeypatch.setattr(module.time, 'sleep', lambda seconds: None)
    return module.capture_log('TEST', duration=2, boot_timeout=2)


def test_preboot_events_excluded_and_split_lines_reassembled(monkeypatch):
    result = run_capture(monkeypatch, [b'LED_OFF timestamp=9000\n',
        b'BOOT_OK interval_ms=500 gpio=4\nLED_ON time', b'stamp=0\n',
        b'LED_OFF timestamp=500\nLED_ON timestamp=1000\n'])
    assert result['success']
    assert '9000' not in result['log'] and '9000' in result['raw_log']
    assert 'LED_ON timestamp=0\n' in result['log']
    assert verify(result['log'], 500, min_cycles=1)['success']


def test_no_boot_is_monitor_failure(monkeypatch):
    result = run_capture(monkeypatch, [b'LED_ON timestamp=500\n'])
    assert not result['success'] and result['log'] == ''


def test_second_boot_is_not_silently_removed(monkeypatch):
    result = run_capture(monkeypatch, [b'BOOT_OK interval_ms=500 gpio=4\n',
        b'LED_ON timestamp=0\nLED_OFF timestamp=500\nLED_ON timestamp=1000\n',
        b'BOOT_OK interval_ms=500 gpio=4\nLED_ON timestamp=0\n'])
    assert result['log'].count('BOOT_OK') == 2
    assert not verify(result['log'], 500, min_cycles=1)['success']
