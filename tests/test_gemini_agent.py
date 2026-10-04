from types import SimpleNamespace
import pytest
from agent import gemini_agent as module


def setup_tools(monkeypatch):
    edits = []
    monkeypatch.setattr(module, 'read_source', lambda: '#define LED_INTERVAL_MS 500')
    monkeypatch.setattr(module, 'set_interval', lambda value: edits.append(value) or {'success': True})
    monkeypatch.setattr(module, 'build', lambda: {'success': True, 'return_code': 0})
    return edits


def test_order_and_independent_expected_value(monkeypatch):
    edits = setup_tools(monkeypatch)
    session = module.ToolSession(1000)
    assert session.execute('inspect_firmware', {})['success']
    assert not session.execute('set_led_interval', {'interval_ms': 500})['success']
    assert edits == []


@pytest.mark.parametrize('name,args', [('flash', {}), ('build_firmware', {}),
    ('set_led_interval', {'interval_ms': 1000}), ('inspect_firmware', {'path': '.env'})])
def test_unauthorized_or_out_of_order_calls_rejected(monkeypatch, name, args):
    setup_tools(monkeypatch)
    assert not module.ToolSession(1000).execute(name, args)['success']


def test_successful_sequence(monkeypatch):
    edits = setup_tools(monkeypatch)
    session = module.ToolSession(1000)
    assert session.execute('inspect_firmware', {})['success']
    assert session.execute('set_led_interval', {'interval_ms': 1000.0})['success']
    assert session.execute('build_firmware', {})['success']
    assert session.phase == 'built' and edits == [1000]


def fake_client(responses):
    calls = []
    def generate(**kwargs):
        calls.append(kwargs)
        return responses.pop(0)
    return SimpleNamespace(models=SimpleNamespace(generate_content=generate)), calls


def reply(part):
    from google.genai import types
    content = types.Content(role='model', parts=[part])
    return SimpleNamespace(candidates=[SimpleNamespace(content=content)])


def test_function_loop_preserves_signature_and_call_id(monkeypatch):
    from google.genai import types
    setup_tools(monkeypatch)
    first = reply(types.Part(function_call=types.FunctionCall(name='inspect_firmware', args={}, id='inspect-1'),
                             thought_signature=b'opaque-signature'))
    client, calls = fake_client([first,
        reply(types.Part.from_function_call(name='set_led_interval', args={'interval_ms': 1000})),
        reply(types.Part.from_function_call(name='build_firmware', args={})),
        reply(types.Part.from_text(text='Build complete; hardware pending.'))])
    result = module.run_agent(client, 'gemini-3.8-flash', 'Set interval to 1000ms', 1000)
    assert result['success'] and len(result['tool_calls']) == 3
    assert calls[0]['config'].temperature is None
    assert calls[0]['config'].thinking_config.thinking_level == 'LOW'
    assert calls[1]['contents'][1] is first.candidates[0].content
    assert calls[1]['contents'][2].parts[0].function_response.id == 'inspect-1'
    assert calls[3]['config'].tool_config.function_calling_config.mode == 'NONE'


def test_text_claim_alone_cannot_pass(monkeypatch):
    from google.genai import types
    setup_tools(monkeypatch)
    client, _ = fake_client([reply(types.Part.from_text(text='Everything passed!'))])
    assert not module.run_agent(client, 'test-model', 'Set interval', 1000)['success']


def test_failed_build_returns_failure(monkeypatch):
    setup_tools(monkeypatch)
    monkeypatch.setattr(module, 'build', lambda: {'success': False, 'return_code': 2})
    session = module.ToolSession(1000)
    session.execute('inspect_firmware', {})
    session.execute('set_led_interval', {'interval_ms': 1000})
    assert not session.execute('build_firmware', {})['success']
    assert session.phase == 'failed'
