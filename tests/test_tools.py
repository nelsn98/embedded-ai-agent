import subprocess
import pytest
from tools import common, file_tools
from tools.monitor_tool import capture_log


def test_missing_idf_environment(monkeypatch):
    monkeypatch.delenv('IDF_PATH', raising=False)
    assert not common.run_idf(['build'], 1)['success']


def test_idf_timeout_returns_failure(monkeypatch, tmp_path):
    script = tmp_path / 'tools' / 'idf.py'
    script.parent.mkdir()
    script.write_text('')
    monkeypatch.setenv('IDF_PATH', str(tmp_path))
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 1, output=b'partial log')
    monkeypatch.setattr(common.subprocess, 'run', timeout)
    result = common.run_idf(['build'], 1)
    assert not result['success']
    assert result['stdout'] == 'partial log'
    assert 'timed out' in result['stderr']


def test_parameter_edit_is_limited(monkeypatch, tmp_path):
    source = tmp_path / 'firmware.c'
    source.write_text('#define LED_INTERVAL_MS 500\nvoid app_main(void) {}\n')
    monkeypatch.setattr(file_tools, 'SOURCE_PATH', source)
    file_tools.set_interval(1000)
    assert source.read_text() == '#define LED_INTERVAL_MS 1000\nvoid app_main(void) {}\n'
    for value in [0, 2001, True, 500.5, '500']:
        with pytest.raises(ValueError):
            file_tools.set_interval(value)
    source.write_text('#define LED_INTERVAL_MS 500\n#define LED_INTERVAL_MS 500\n')
    with pytest.raises(ValueError):
        file_tools.set_interval(1000)
    assert source.read_text().count('500') == 2


def test_serial_disconnect_closes_port(monkeypatch):
    import serial
    closed = []
    class Device:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            closed.append(True)
        def reset_input_buffer(self):
            pass
        def readline(self):
            raise serial.SerialException('Device disconnected')
    monkeypatch.setattr(serial, 'Serial', lambda *args, **kwargs: Device())
    result = capture_log('COM_TEST', 1)
    assert not result['success'] and closed
