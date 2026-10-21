"""
The AI can talk to Anthropic directly, or through OpenRouter. Both are asked
the same questions and must answer in the same way; these tests check that the
request goes to the right service, in the shape that service expects, and that
its reply is read back correctly.
"""
import json
import re

import app as A


# ── the provider in use ──────────────────────────────────────────────────────

def test_the_provider_is_anthropic_until_another_is_picked():
    assert A.ai_provider() == "anthropic"


def test_an_unknown_provider_falls_back_to_anthropic():
    A.CONFIG["ai_provider"] = "not-a-provider"
    assert A.ai_provider() == "anthropic"


def test_the_key_of_the_provider_in_use_is_the_one_that_counts():
    A.CONFIG.update(anthropic_api_key="sk-ant", openrouter_api_key="sk-or")
    assert A._ai_key() == "sk-ant"
    A.CONFIG["ai_provider"] = "openrouter"
    assert A._ai_key() == "sk-or"


def test_the_ai_is_on_when_the_provider_in_use_has_a_key():
    A.CONFIG.update(anthropic_api_key="sk-ant", openrouter_api_key="")
    assert A.ai_active() is True
    A.CONFIG["ai_provider"] = "openrouter"
    assert A.ai_active() is False        # the other key does not stand in for it


def test_the_model_follows_the_provider():
    assert A._ai_model("main") == A.MODEL_MAIN
    assert A._ai_model("fast") == A.MODEL_FAST
    A.CONFIG["ai_provider"] = "openrouter"
    assert A._ai_model("main") == "anthropic/claude-sonnet-5"
    assert A._ai_model("fast") == "anthropic/claude-haiku-4.5"


def test_the_openrouter_models_can_be_chosen():
    A.CONFIG.update(ai_provider="openrouter",
                    openrouter_model_main="openai/gpt-5.4",
                    openrouter_model_fast="google/gemini-3.5-flash")
    assert A._ai_model("main") == "openai/gpt-5.4"
    assert A._ai_model("fast") == "google/gemini-3.5-flash"


# ── where the call goes ──────────────────────────────────────────────────────

class _FakeResponse:
    def __init__(self, body):
        self.body = body
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def read(self):
        return json.dumps(self.body).encode()


def _capture(monkeypatch):
    """Keep the request that leaves MedSearch, and answer it with a fake."""
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen["request"] = req
        return _FakeResponse(seen.get("body", {}))
    monkeypatch.setattr(A.urllib.request, "urlopen", fake_urlopen)
    return seen


def test_the_call_goes_to_openrouter_with_its_key(monkeypatch):
    A.CONFIG.update(ai_provider="openrouter", openrouter_api_key="sk-or-1")
    _capture(monkeypatch)
    A.ai_text({"model": "anthropic/claude-sonnet-5", "max_tokens": 10, "messages": []})
    assert A.PROVIDERS["openrouter"]["url"] == "https://openrouter.ai/api/v1/chat/completions"


def test_the_anthropic_call_keeps_its_own_headers(monkeypatch):
    A.CONFIG.update(ai_provider="anthropic", anthropic_api_key="sk-ant-1")
    seen = _capture(monkeypatch)
    A.ai_text({"model": A.MODEL_MAIN, "max_tokens": 10, "messages": []})
    req = seen["request"]
    assert req.full_url == A.ANTHROPIC_URL
    assert req.get_header("X-api-key") == "sk-ant-1"
    assert req.get_header("Anthropic-version") == "2023-06-01"


def test_the_openrouter_call_carries_the_key_as_a_bearer_token(monkeypatch):
    A.CONFIG.update(ai_provider="openrouter", openrouter_api_key="sk-or-1")
    seen = _capture(monkeypatch)
    A.ai_text({"model": "anthropic/claude-sonnet-5", "max_tokens": 10, "messages": []})
    req = seen["request"]
    assert req.full_url == A.OPENROUTER_URL
    assert req.get_header("Authorization") == "Bearer sk-or-1"
    assert req.get_header("Anthropic-version") is None


def test_the_openrouter_request_is_in_the_shape_it_expects(monkeypatch):
    A.CONFIG.update(ai_provider="openrouter", openrouter_api_key="sk-or-1")
    seen = _capture(monkeypatch)
    A.ai_text({"model": "anthropic/claude-sonnet-5", "max_tokens": 10,
               "thinking": {"type": "disabled"},
               "system": [{"type": "text", "text": "SYS"},
                          {"type": "text", "text": "CTX",
                           "cache_control": {"type": "ephemeral"}}],
               "messages": [{"role": "user", "content": "hello"}]})
    body = json.loads(seen["request"].data.decode())
    # The system prompt becomes a message of its own, and the Anthropic-only
    # fields are gone.
    assert body["messages"] == [{"role": "system", "content": "SYS\n\nCTX"},
                                {"role": "user", "content": "hello"}]
    assert "thinking" not in body
    assert "system" not in body


def test_the_anthropic_request_is_untouched(monkeypatch):
    A.CONFIG.update(ai_provider="anthropic", anthropic_api_key="sk-ant-1")
    seen = _capture(monkeypatch)
    A.ai_text({"model": A.MODEL_MAIN, "max_tokens": 10,
               "system": [{"type": "text", "text": "SYS"}],
               "messages": [{"role": "user", "content": "hello"}]})
    body = json.loads(seen["request"].data.decode())
    assert body["system"] == [{"type": "text", "text": "SYS"}]
    assert body["messages"] == [{"role": "user", "content": "hello"}]


# ── reading the reply ────────────────────────────────────────────────────────

def test_the_anthropic_reply_is_read(monkeypatch):
    A.CONFIG.update(ai_provider="anthropic", anthropic_api_key="sk-ant-1")
    seen = _capture(monkeypatch)
    seen["body"] = {"content": [{"type": "text", "text": "Hello there"}],
                    "usage": {"input_tokens": 10, "output_tokens": 5}}
    assert A.ai_text({"model": A.MODEL_MAIN, "max_tokens": 10, "messages": []}) == "Hello there"


def test_the_openrouter_reply_is_read(monkeypatch):
    A.CONFIG.update(ai_provider="openrouter", openrouter_api_key="sk-or-1")
    seen = _capture(monkeypatch)
    seen["body"] = {"choices": [{"message": {"role": "assistant", "content": "Hello there"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
    assert A.ai_text({"model": "anthropic/claude-sonnet-5", "max_tokens": 10,
                      "messages": []}) == "Hello there"


def test_a_refusal_is_reported_whichever_provider(monkeypatch):
    A.CONFIG.update(ai_provider="anthropic", anthropic_api_key="sk-ant-1")
    seen = _capture(monkeypatch)
    seen["body"] = {"stop_reason": "refusal", "content": []}
    try:
        A.ai_text({"model": A.MODEL_MAIN, "max_tokens": 10, "messages": []})
    except RuntimeError as e:
        assert "declined" in str(e)
    else:
        raise AssertionError("the refusal went unreported")

    A.CONFIG.update(ai_provider="openrouter", openrouter_api_key="sk-or-1")
    seen["body"] = {"choices": [{"message": {"refusal": "no"}}]}
    try:
        A.ai_text({"model": "anthropic/claude-sonnet-5", "max_tokens": 10, "messages": []})
    except RuntimeError as e:
        assert "declined" in str(e)
    else:
        raise AssertionError("the refusal went unreported")


def test_the_cost_openrouter_reports_is_the_cost(monkeypatch, tmp_path):
    monkeypatch.setattr(A, "USAGE_FILE", tmp_path / "usage.json")
    A.CONFIG.update(ai_provider="openrouter", openrouter_api_key="sk-or-1")
    seen = _capture(monkeypatch)
    seen["body"] = {"choices": [{"message": {"content": "hi"}}],
                    "usage": {"prompt_tokens": 1000, "completion_tokens": 500, "cost": 0.0042}}
    A.ai_text({"model": "some/model", "max_tokens": 10, "messages": []},
              feature="syntheses")
    used = A.load_usage()
    # The figure the provider gave is the one kept, not a price worked out here.
    assert round(used["cost"], 6) == 0.0042
    assert used["unpriced_calls"] == 0
    assert used["input_tokens"] == 1000
    assert used["output_tokens"] == 500


def test_without_a_cost_the_call_is_priced_from_the_model(monkeypatch, tmp_path):
    monkeypatch.setattr(A, "USAGE_FILE", tmp_path / "usage.json")
    A.CONFIG.update(ai_provider="openrouter", openrouter_api_key="sk-or-1")
    seen = _capture(monkeypatch)
    seen["body"] = {"choices": [{"message": {"content": "hi"}}],
                    "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 100_000}}
    A.ai_text({"model": "anthropic/claude-sonnet-5", "max_tokens": 10, "messages": []},
              feature="syntheses")
    assert round(A.load_usage()["cost"], 2) == 3.00


# ── the stream ───────────────────────────────────────────────────────────────

class _FakeStream:
    def __init__(self, lines):
        self.lines = [l.encode() for l in lines]
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def __iter__(self):
        return iter(self.lines)


def _events(monkeypatch, lines):
    monkeypatch.setattr(A, "_ai_open", lambda payload, timeout: _FakeStream(lines))
    return [json.loads(c[6:]) for c in A.ai_stream({"model": "m", "messages": []})]


def test_the_anthropic_stream_is_read_as_before(monkeypatch):
    A.CONFIG.update(ai_provider="anthropic", anthropic_api_key="sk-ant-1")
    evs = _events(monkeypatch, [
        'data: {"type":"message_start"}',
        'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hello"}}',
        'data: {"type":"message_stop"}'])
    assert evs == [{"type": "chunk", "text": "Hello"}, {"type": "done"}]


def test_the_openrouter_stream_is_read(monkeypatch):
    A.CONFIG.update(ai_provider="openrouter", openrouter_api_key="sk-or-1")
    evs = _events(monkeypatch, [
        'data: {"choices":[{"delta":{"content":"Hel"}}]}',
        'data: {"choices":[{"delta":{"content":"lo"}}]}',
        'data: {"choices":[],"usage":{"prompt_tokens":10,"completion_tokens":2}}',
        'data: [DONE]'])
    assert evs == [{"type": "chunk", "text": "Hel"}, {"type": "chunk", "text": "lo"},
                   {"type": "done"}]


def test_an_error_in_the_openrouter_stream_is_reported(monkeypatch):
    A.CONFIG.update(ai_provider="openrouter", openrouter_api_key="sk-or-1")
    evs = _events(monkeypatch, ['data: {"error":{"message":"no credit left"}}'])
    assert evs[0] == {"type": "error", "text": "no credit left"}
    assert evs[-1] == {"type": "done"}


def test_the_openrouter_stream_is_metered(monkeypatch, tmp_path):
    monkeypatch.setattr(A, "USAGE_FILE", tmp_path / "usage.json")
    A.CONFIG.update(ai_provider="openrouter", openrouter_api_key="sk-or-1")
    evs = _events(monkeypatch, [
        'data: {"choices":[{"delta":{"content":"Hi"}}]}',
        'data: {"choices":[],"usage":{"prompt_tokens":100,"completion_tokens":20,"cost":0.001}}'])
    assert evs[0] == {"type": "chunk", "text": "Hi"}
    used = A.load_usage()
    assert used["input_tokens"] == 100
    assert used["output_tokens"] == 20
    assert round(used["cost"], 6) == 0.001


def test_no_key_is_an_error_under_either_provider():
    A.CONFIG.update(anthropic_api_key="", openrouter_api_key="")
    for provider in ("anthropic", "openrouter"):
        A.CONFIG["ai_provider"] = provider
        evs = [json.loads(c[6:]) for c in A.ai_stream({"messages": []})]
        assert evs[0]["type"] == "error" and evs[-1]["type"] == "done"
        assert A.PROVIDERS[provider]["label"] in evs[0]["text"]


# ── the settings ─────────────────────────────────────────────────────────────

def test_the_provider_and_the_models_are_saved(client, auth, tmp_path, monkeypatch):
    monkeypatch.setattr(A, "CONFIG_FILE", tmp_path / "config.json")
    res = client.post("/settings", headers=auth, json={
        "ai_provider": "openrouter",
        "openrouter_model_main": "openai/gpt-5.4",
        "openrouter_model_fast": "google/gemini-3.5-flash"})
    assert res.get_json()["ok"] is True
    assert A.CONFIG["ai_provider"] == "openrouter"
    assert A.CONFIG["openrouter_model_main"] == "openai/gpt-5.4"


def test_an_unknown_provider_is_not_saved(client, auth):
    client.post("/settings", headers=auth, json={"ai_provider": "not-a-provider"})
    assert A.CONFIG["ai_provider"] == "anthropic"


def test_the_settings_page_reports_the_provider_and_the_models(client, auth):
    A.CONFIG.update(ai_provider="openrouter",
                    openrouter_model_main="openai/gpt-5.4",
                    openrouter_model_fast="google/gemini-3.5-flash")
    s = client.get("/settings", headers=auth).get_json()
    assert s["ai_provider"] == "openrouter"
    assert s["openrouter_model_main"] == "openai/gpt-5.4"
    assert s["openrouter_model_fast"] == "google/gemini-3.5-flash"


def test_the_key_of_the_provider_in_use_is_what_the_page_reports(client, auth):
    A.CONFIG.update(ai_provider="openrouter", openrouter_api_key="", anthropic_api_key="sk-ant")
    assert client.get("/settings", headers=auth).get_json()["has_ai_key"] is False
    A.CONFIG["openrouter_api_key"] = "sk-or"
    assert client.get("/settings", headers=auth).get_json()["has_ai_key"] is True


def test_the_openrouter_models_are_named_as_openrouter_names_them():
    # OpenRouter writes the version with a dot (anthropic/claude-haiku-4.5);
    # the hyphen form Anthropic itself uses is no model there.
    for model in (A.OPENROUTER_MODEL_MAIN, A.OPENROUTER_MODEL_FAST,
                  A.DEFAULTS["openrouter_model_main"], A.DEFAULTS["openrouter_model_fast"]):
        assert re.fullmatch(r"anthropic/claude-[a-z]+-\d+(\.\d+)?", model), model
