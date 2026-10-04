import json
import pytest
from agent import run_demo as module


@pytest.fixture
def rig(monkeypatch, tmp_path):
    source = tmp_path / 'main.c'
    source.write_text('#define LED_INTERVAL_MS 500\n')
    monkeypatch.setattr(module, 'SOURCE_PATH', source)
    calls = []
    def agent(*args):
        source.write_text('#define LED_INTERVAL_MS 1000\n')
        return {'success': True, 'phase': 'built'}
    monkeypatch.setattr(module, 'run_agent', agent)
    monkeypatch.setattr(module, 'flash', lambda port: calls.append('flash') or {'success': True})
    log = 'BOOT_OK interval_ms=1000 gpio=4\n' + ''.join(
        f"LED_{'ON' if i%2==0 else 'OFF'} timestamp={i*1000}\n" for i in range(31))
    monkeypatch.setattr(module, 'capture_log', lambda port, duration: {'success': True, 'log': log, 'raw_log': log})
    def run(approve=lambda port: True):
        return module.run_workflow(None, 'test', '1000ms', 1000, 'TEST', 30,
                                   tmp_path / 'report', approve=approve)
    return run, source, calls, tmp_path / 'report'


def test_full_workflow_and_saved_evidence(rig):
    run, source, calls, output = rig
    result = run()
    assert result['success'] and calls == ['flash']
    assert json.loads((output/'report.json').read_text())['status'] == 'passed'
    assert '500' in (output/'source_before.c').read_text()
    assert '1000' in (output/'source_after.c').read_text()
    assert (output/'device.log').read_text().startswith('BOOT_OK')


def test_declined_flash_is_cancelled(rig):
    run, source, calls, output = rig
    result = run(lambda port: False)
    assert result['status'] == 'cancelled' and not result['success'] and not calls
    assert result['approval'] == 'declined'


def test_failed_agent_cannot_flash(monkeypatch, rig):
    run, source, calls, output = rig
    monkeypatch.setattr(module, 'run_agent', lambda *args: {'success': False, 'error': 'Build failed'})
    assert run()['stage'] == 'agent' and not calls


def test_source_edit_during_confirmation_blocks_flash(rig):
    run, source, calls, output = rig
    def approve(port):
        source.write_text('changed by another process')
        return True
    assert run(approve)['stage'] == 'source_check' and not calls


@pytest.mark.parametrize('stage', ['flash', 'monitor'])
def test_device_failure_stops_following_stages(monkeypatch, rig, stage):
    run, source, calls, output = rig
    name = 'flash' if stage == 'flash' else 'capture_log'
    monkeypatch.setattr(module, name, lambda *args: {'success': False, 'error': 'disconnected'})
    result = run()
    assert not result['success'] and result['stage'] == stage
    assert 'verify' not in result['stages']


def test_wrong_hardware_interval_fails(monkeypatch, rig):
    run, source, calls, output = rig
    log = 'BOOT_OK interval_ms=500 gpio=4\n' + ''.join(
        f"LED_{'ON' if i%2==0 else 'OFF'} timestamp={i*500}\n" for i in range(31))
    monkeypatch.setattr(module, 'capture_log', lambda *args: {'success': True, 'log': log})
    result = run()
    assert not result['success'] and result['stage'] == 'verify'
    assert result['stages']['verify']['checks']['interval'] is False


def test_interruption_preserves_report(rig):
    run, source, calls, output = rig
    def interrupt(port):
        raise KeyboardInterrupt()
    assert run(interrupt)['status'] == 'cancelled'
    assert not calls and (output/'report.json').exists()
