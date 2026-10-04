"""Single entry: Gemini edit/build -> user approval -> flash -> UART verify."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path

from agent.gemini_agent import run_agent
from tools.common import PROJECT_ROOT, SOURCE_PATH
from tools.flash_tool import flash
from tools.monitor_tool import capture_log
from tools.verify_tool import verify


def digest(data):
    return hashlib.sha256(data).hexdigest()


def confirm_flash(port):
    return input(f'Build succeeded. Flash device on {port}? Type FLASH to proceed: ').strip() == 'FLASH'


def run_workflow(client, model, request, expected_ms, port, duration, output,
                 approve=confirm_flash, secret=''):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = {'success': False, 'status': 'running', 'stage': 'prepare',
              'started_at': datetime.now(timezone.utc).isoformat(),
              'model': model, 'request': request, 'expected_ms': expected_ms,
              'port': port, 'duration_s': duration, 'tolerance_ms': 50,
              'approval': 'not_requested', 'stages': {},
              'verification_scope': 'UART software behavior; GPIO voltage and optical output unmeasured'}

    def clean(text):
        return text.replace(secret, '[REDACTED]') if secret else text

    def checkpoint():
        text = clean(json.dumps(report, ensure_ascii=False, indent=2))
        temporary = output / 'report.tmp'
        temporary.write_text(text, encoding='utf-8')
        temporary.replace(output / 'report.json')

    try:
        if type(expected_ms) is not int or not 100 <= expected_ms <= 2000:
            raise ValueError('expected_ms must be 100..2000')
        minimum = 20 * expected_ms / 1000 + 2
        if not math.isfinite(duration) or duration < minimum:
            raise ValueError(f'duration must be at least {minimum:g} seconds for 10 full cycles')
        before = SOURCE_PATH.read_bytes()
        (output / 'source_before.c').write_bytes(before)
        report['source_before_sha256'] = digest(before)
        report['stage'] = 'agent'
        checkpoint()
        agent_result = run_agent(client, model, request, expected_ms)
        report['stages']['agent'] = agent_result
        after = SOURCE_PATH.read_bytes()
        (output / 'source_after.c').write_bytes(after)
        report['source_after_sha256'] = digest(after)
        checkpoint()
        if not agent_result['success']:
            report.update(status='failed', error=agent_result.get('error', 'Agent failed'))
            return report
        report['stage'] = 'approval'
        report['approval'] = 'pending'
        checkpoint()
        if not approve(port):
            report.update(status='cancelled', approval='declined',
                          error='Flashing cancelled; source changes and successful build are retained')
            return report
        report['approval'] = 'approved'
        report['stage'] = 'source_check'
        if digest(SOURCE_PATH.read_bytes()) != report['source_after_sha256']:
            report.update(status='failed', error='Firmware source changed after Agent build; rerun before flashing')
            return report
        for name, action in [('flash', lambda: flash(port)),
                             ('monitor', lambda: capture_log(port, duration)),
                             ('verify', lambda: verify(report['stages']['monitor']['log'], expected_ms, 50))]:
            report['stage'] = name
            checkpoint()
            print(name.upper(), flush=True)
            result = action()
            report['stages'][name] = result
            checkpoint()
            if not result['success']:
                report.update(status='failed', error=f'{name} failed; inspect stages.{name}')
                return report
        report.update(success=True, status='passed', stage='complete')
        return report
    except (KeyboardInterrupt, EOFError):
        report.update(status='cancelled', error='Interrupted by user or terminal input closed')
        return report
    except Exception as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        return report
    finally:
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        monitor = report['stages'].get('monitor', {})
        (output / 'device.log').write_text(clean(monitor.get('log', '')), encoding='utf-8')
        (output / 'raw_device.log').write_text(clean(monitor.get('raw_log', '')), encoding='utf-8')
        checkpoint()
        checks = report['stages'].get('verify', {}).get('checks', {})
        summary = ['# Embedded Agent Lab run', '', f"Status: {report['status']}",
                   f"Stage: {report['stage']}", f"Expected transition interval: {expected_ms} ms",
                   f"Port: {port}", f"Flash approval: {report['approval']}", '',
                   '| Check | Result |', '| --- | --- |']
        summary += [f'| {name} | {"PASS" if passed else "FAIL"} |' for name, passed in checks.items()]
        summary += ['', report.get('error', ''), '', report['verification_scope']]
        (output / 'summary.md').write_text(clean('\n'.join(summary)), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True)
    parser.add_argument('--expected-ms', required=True, type=int)
    parser.add_argument('--port', required=True)
    parser.add_argument('--model', default=None)
    parser.add_argument('--duration', type=float, default=None)
    args = parser.parse_args()
    if not 100 <= args.expected_ms <= 2000:
        parser.error('--expected-ms must be 100..2000')
    duration = args.duration if args.duration is not None else max(20, 20 * args.expected_ms / 1000 + 5)
    if not math.isfinite(duration) or duration < 20 * args.expected_ms / 1000 + 2:
        parser.error('--duration must allow 10 full cycles plus 2 seconds')
    try:
        from dotenv import load_dotenv
        from google import genai
        from google.genai import types
    except ImportError:
        print('Install dependencies: python -m pip install -r requirements-day3.txt')
        return 1
    load_dotenv(PROJECT_ROOT / '.env', override=False)
    key = os.environ.get('GEMINI_API_KEY')
    if not key:
        print('GEMINI_API_KEY missing; configure your local .env')
        return 1
    if not os.environ.get('IDF_PATH'):
        print('IDF_PATH missing; open the ESP-IDF terminal')
        return 1
    model = args.model or os.environ.get('GEMINI_MODEL', 'gemini-3.8-flash')
    output = PROJECT_ROOT / 'reports' / ('demo_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    with genai.Client(api_key=key, http_options=types.HttpOptions(timeout=60000)) as client:
        report = run_workflow(client, model, args.request, args.expected_ms,
                              args.port, duration, output, secret=key)
    print('DEMO PASS' if report['success'] else f"DEMO {report['status'].upper()}: {report['stage']}")
    if report.get('error'):
        print(report['error'].replace(key, '[REDACTED]'))
    print('Report:', output / 'report.json')
    return 0 if report['success'] else 2 if report['status'] == 'cancelled' else 1


if __name__ == '__main__':
    raise SystemExit(main())
