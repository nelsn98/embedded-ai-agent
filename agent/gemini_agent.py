"""Day 2: Gemini function calling, restricted to inspect -> set -> build."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from tools.common import PROJECT_ROOT
from tools.file_tools import read_source, set_interval
from tools.build_tool import build

DECLARATIONS = [
    {'name': 'inspect_firmware', 'description': 'Read the single allowed ESP32 firmware source before editing.',
     'parameters': {'type': 'OBJECT', 'properties': {}}},
    {'name': 'set_led_interval', 'description': 'Set ON/OFF transition interval in milliseconds; one full blink cycle is twice this value.',
     'parameters': {'type': 'OBJECT', 'properties': {'interval_ms': {'type': 'INTEGER', 'minimum': 100, 'maximum': 2000}},
                    'required': ['interval_ms']}},
    {'name': 'build_firmware', 'description': 'Build edited ESP32 firmware using ESP-IDF. Does not flash the device.',
     'parameters': {'type': 'OBJECT', 'properties': {}}},
]
SYSTEM = '''You are an embedded development assistant for a narrow LED demo.
Use tools in order: inspect_firmware, set_led_interval, build_firmware.
Never claim an action happened without a successful tool result.
The user's transition interval must match the independently supplied expected_ms.
If the natural-language request conflicts with expected_ms or is ambiguous, explain and stop without editing.
An interval of 1000 ms means ON for 1000 ms, then OFF for 1000 ms (a 2000 ms full cycle).
Do not edit any other code, invoke shell commands, flash hardware, or change test expectations.
Stop on any tool failure. After a successful build, summarize in Traditional Chinese.
State that only source modification and build were verified; hardware verification is pending.
'''


class ToolSession:
    def __init__(self, expected_ms):
        if type(expected_ms) is not int or not 100 <= expected_ms <= 2000:
            raise ValueError('expected_ms must be an integer from 100 to 2000')
        self.expected_ms = expected_ms
        self.phase = 'initial'
        self.events = []

    def execute(self, name, args):
        args = args or {}
        try:
            if name == 'inspect_firmware':
                if args or self.phase != 'initial':
                    raise ValueError('inspect_firmware requires no arguments and must run first')
                result = {'success': True, 'source': read_source()}
                self.phase = 'inspected'
            elif name == 'set_led_interval':
                if self.phase != 'inspected' or set(args) != {'interval_ms'}:
                    raise ValueError('Inspect first; only interval_ms is allowed')
                value = args['interval_ms']
                # Some SDK JSON decoders expose integer schema values as floats.
                if type(value) is float and value.is_integer():
                    value = int(value)
                if type(value) is not int or value != self.expected_ms:
                    raise ValueError('Requested tool value must match independent expected_ms')
                result = set_interval(value)
                self.phase = 'modified'
            elif name == 'build_firmware':
                if args or self.phase != 'modified':
                    raise ValueError('Modify first; build_firmware takes no arguments')
                result = build()
                self.phase = 'built' if result['success'] else 'failed'
            else:
                raise ValueError('Unknown tool: ' + str(name))
        except (ValueError, OSError) as exc:
            result = {'success': False, 'error': str(exc)}
            self.phase = 'failed'
        self.events.append({'timestamp': datetime.now(timezone.utc).isoformat(),
                            'tool': name, 'arguments': args, 'result': result})
        print('TOOL:', name, args, '->', 'OK' if result['success'] else 'FAIL', flush=True)
        return result


def model_result(result):
    # Keep complete compiler output in the local report, but send a short result to Gemini.
    return {key: value[-4000:] if key in ('stdout', 'stderr') and isinstance(value, str) else value
            for key, value in result.items()}


def run_agent(client, model, request, expected_ms, max_rounds=8):
    from google.genai import types
    session = ToolSession(expected_ms)
    history = [types.Content(role='user', parts=[types.Part.from_text(
        text=f'Independent acceptance parameter expected_ms={expected_ms}. User request: {request}')])]
    summary = ''
    error = ''
    for _ in range(max_rounds):
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM,
            tools=[types.Tool(function_declarations=DECLARATIONS)],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(
                mode='NONE' if session.phase == 'built' else 'AUTO')),
            thinking_config=types.ThinkingConfig(thinking_level="low")
            if model.startswith("gemini-3") else None,
            max_output_tokens=2048,
        )
        try:
            response = client.models.generate_content(model=model, contents=history, config=config)
        except Exception as exc:
            error = f'Gemini API error ({type(exc).__name__}): {exc}'
            break
        if not response.candidates or not response.candidates[0].content:
            error = 'Model returned no usable content (possibly blocked or empty response)'
            break
        content = response.candidates[0].content
        # Preserve the original model content, including thought signatures.
        history.append(content)
        calls = [part.function_call for part in (content.parts or []) if part.function_call]
        if not calls:
            summary = ''.join(part.text or '' for part in (content.parts or []) if not part.thought)
            if session.phase != 'built':
                error = 'Model stopped before a successful tool build; task is incomplete'
            break
        responses = []
        for call in calls:
            result = session.execute(call.name, dict(call.args or {}))
            if not result['success']:
                error = 'Tool failed: ' + call.name
                break
            fr = types.FunctionResponse(name=call.name, response=model_result(result))
            if call.id:
                fr.id = call.id
            responses.append(types.Part(function_response=fr))
        if error:
            break
        history.append(types.Content(role='user', parts=responses))
    else:
        error = 'Maximum model rounds reached; no automatic retry'
    return {'success': session.phase == 'built' and not error,
            'phase': session.phase, 'expected_ms': expected_ms, 'model': model,
            'request': request, 'summary': summary, 'error': error, 'tool_calls': session.events,
            'verification_scope': 'Source parameter change and ESP-IDF build only; device not flashed or verified'}


def main():
    parser = argparse.ArgumentParser(description='Gemini LED parameter editing and ESP-IDF build')
    parser.add_argument('--request', required=True)
    parser.add_argument('--expected-ms', required=True, type=int)
    parser.add_argument('--model', default=None)
    args = parser.parse_args()
    if not 100 <= args.expected_ms <= 2000:
        parser.error('--expected-ms must be 100..2000')
    try:
        from dotenv import load_dotenv
        from google import genai
    except ImportError:
        print('Install Day 2 dependencies: python -m pip install -r requirements-day2.txt')
        return 1
    load_dotenv(PROJECT_ROOT / '.env', override=False)
    key = os.environ.get('GEMINI_API_KEY')
    if not key:
        print('GEMINI_API_KEY missing. Set it in your local .env; do not share the key.')
        return 1
    if not os.environ.get('IDF_PATH'):
        print('IDF_PATH missing. Open the ESP-IDF terminal first.')
        return 1
    model = args.model or os.environ.get('GEMINI_MODEL', 'gemini-3.8-flash')
    from google.genai import types
    with genai.Client(api_key=key, http_options=types.HttpOptions(timeout=60000)) as client:
        report = run_agent(client, model, args.request, args.expected_ms)
    # Avoid accidentally persisting the configured credential in API error messages.
    report['error'] = report['error'].replace(key, '[REDACTED]')
    output = PROJECT_ROOT / 'reports' / ('agent_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    output.mkdir(parents=True)
    path = output / 'agent_report.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(report['summary'] or report['error'])
    print('AGENT BUILD PASS' if report['success'] else 'AGENT FAIL')
    print('Report:', path)
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
