"""Tests for server routing and /responses normalization."""

import pytest

from codex_proxy.server import (
    _aggregate_nonstream_chat_completion,
    _normalize_responses_body,
    _parse_sse_data_line,
    create_app,
    handle_chat_completions,
    handle_responses,
)


def _post_paths() -> set[str]:
    app = create_app()
    paths: set[str] = set()
    for route in app.router.routes():
        if route.method != "POST":
            continue
        path = route.resource.get_info().get("path")
        if path:
            paths.add(path)
    return paths


def test_post_routes_include_chat_completions_and_responses():
    paths = _post_paths()
    assert "/v1/chat/completions" in paths
    assert "/chat/completions" in paths
    assert "/v1/responses" in paths
    assert "/responses" in paths


def test_normalize_responses_body_drops_max_output_tokens_and_sets_defaults():
    body, client_stream = _normalize_responses_body(
        {
            "model": "gpt-5.3-codex",
            "input": "hi",
            "max_output_tokens": 256,
            "max_completion_tokens": 123,
            "stream": False,
        }
    )
    assert client_stream is False
    assert "max_output_tokens" not in body
    assert "max_completion_tokens" not in body
    assert body["instructions"] == "You are a helpful assistant."
    assert body["store"] is False
    assert body["stream"] is True
    assert body["input"] == [
        {"role": "user", "content": [{"type": "input_text", "text": "hi"}]}
    ]


def test_normalize_responses_body_keeps_existing_values():
    body, client_stream = _normalize_responses_body(
        {
            "model": "gpt-5.3-codex",
            "input": [{"role": "user", "content": [{"type": "input_text", "text": "hi"}]}],
            "instructions": "Custom instruction",
            "store": False,
            "stream": True,
        }
    )
    assert client_stream is True
    assert body["instructions"] == "Custom instruction"
    assert body["store"] is False
    assert body["stream"] is True


def test_normalize_responses_body_converts_chat_style_tools_and_tool_choice():
    body, _ = _normalize_responses_body(
        {
            "model": "gpt-5.3-codex",
            "input": "hi",
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "search_docs",
                        "description": "Search docs",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
            "tool_choice": {
                "type": "function",
                "function": {"name": "search_docs"},
            },
        }
    )

    assert body["tools"] == [
        {
            "type": "function",
            "name": "search_docs",
            "description": "Search docs",
            "parameters": {"type": "object", "properties": {}},
            "strict": False,
        }
    ]
    assert body["tool_choice"] == {"type": "function", "name": "search_docs"}


def test_normalize_responses_body_keeps_responses_style_tools_unchanged():
    body, _ = _normalize_responses_body(
        {
            "model": "gpt-5.3-codex",
            "input": "hi",
            "tools": [
                {
                    "type": "function",
                    "name": "search_docs",
                    "description": "Search docs",
                    "parameters": {"type": "object"},
                    "strict": True,
                }
            ],
            "tool_choice": {"type": "function", "name": "search_docs"},
        }
    )

    assert body["tools"] == [
        {
            "type": "function",
            "name": "search_docs",
            "description": "Search docs",
            "parameters": {"type": "object"},
            "strict": True,
        }
    ]
    assert body["tool_choice"] == {"type": "function", "name": "search_docs"}


def test_normalize_responses_body_normalizes_litellm_input_and_strict_null():
    body, _ = _normalize_responses_body(
        {
            "model": "gpt-5.3-codex",
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "hi"}],
                },
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "text", "text": "hello"}],
                },
            ],
            "tools": [
                {
                    "type": "function",
                    "name": "search_docs",
                    "description": "Search docs",
                    "parameters": {"type": "object"},
                    "strict": None,
                }
            ],
        }
    )

    assert body["input"] == [
        {
            "role": "user",
            "content": [{"type": "input_text", "text": "hi"}],
        },
        {
            "role": "assistant",
            "content": [{"type": "input_text", "text": "hello"}],
        },
    ]
    assert body["tools"] == [
        {
            "type": "function",
            "name": "search_docs",
            "description": "Search docs",
            "parameters": {"type": "object"},
            "strict": False,
        }
    ]
    assert body["parallel_tool_calls"] is False


def test_normalize_responses_body_keeps_explicit_parallel_tool_calls():
    body, _ = _normalize_responses_body(
        {
            "model": "gpt-5.3-codex",
            "input": "hi",
            "tools": [
                {
                    "type": "function",
                    "name": "search_docs",
                    "description": "Search docs",
                    "parameters": {"type": "object"},
                }
            ],
            "parallel_tool_calls": True,
        }
    )

    assert body["parallel_tool_calls"] is True


def test_parse_sse_data_line_extracts_payload():
    assert _parse_sse_data_line("data: {\"ok\":true}\n\n") == "{\"ok\":true}"
    assert _parse_sse_data_line("event: ping") is None


def test_aggregate_nonstream_chat_completion_text():
    completion = _aggregate_nonstream_chat_completion(
        [
            {
                "id": "chatcmpl-test",
                "object": "chat.completion.chunk",
                "created": 123,
                "model": "gpt-5.3-codex",
                "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}],
            },
            {
                "id": "chatcmpl-test",
                "object": "chat.completion.chunk",
                "created": 123,
                "model": "gpt-5.3-codex",
                "choices": [{"index": 0, "delta": {"content": "Hel"}, "finish_reason": None}],
            },
            {
                "id": "chatcmpl-test",
                "object": "chat.completion.chunk",
                "created": 123,
                "model": "gpt-5.3-codex",
                "choices": [{"index": 0, "delta": {"content": "lo"}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 2,
                    "total_tokens": 3,
                    "prompt_tokens_details": {"cached_tokens": 0},
                },
            },
        ]
    )
    assert completion is not None
    assert completion["object"] == "chat.completion"
    assert completion["model"] == "gpt-5.3-codex"
    assert completion["choices"][0]["message"]["role"] == "assistant"
    assert completion["choices"][0]["message"]["content"] == "Hello"
    assert completion["choices"][0]["finish_reason"] == "stop"
    assert completion["usage"]["total_tokens"] == 3


def test_aggregate_nonstream_chat_completion_tool_calls():
    completion = _aggregate_nonstream_chat_completion(
        [
            {
                "id": "chatcmpl-tool",
                "object": "chat.completion.chunk",
                "created": 456,
                "model": "gpt-5.3-codex",
                "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
            },
            {
                "id": "chatcmpl-tool",
                "object": "chat.completion.chunk",
                "created": 456,
                "model": "gpt-5.3-codex",
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "fc_123",
                                    "type": "function",
                                    "function": {"name": "search_docs", "arguments": ""},
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ],
            },
            {
                "id": "chatcmpl-tool",
                "object": "chat.completion.chunk",
                "created": 456,
                "model": "gpt-5.3-codex",
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [{"index": 0, "function": {"arguments": '{"q":"hel'}}]
                        },
                        "finish_reason": None,
                    }
                ],
            },
            {
                "id": "chatcmpl-tool",
                "object": "chat.completion.chunk",
                "created": 456,
                "model": "gpt-5.3-codex",
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [{"index": 0, "function": {"arguments": 'lo"}'}}]
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
            },
        ]
    )
    assert completion is not None
    message = completion["choices"][0]["message"]
    assert message["role"] == "assistant"
    assert message["content"] is None
    assert message["tool_calls"][0]["id"] == "fc_123"
    assert message["tool_calls"][0]["function"]["name"] == "search_docs"
    assert message["tool_calls"][0]["function"]["arguments"] == '{"q":"hello"}'
    assert completion["choices"][0]["finish_reason"] == "tool_calls"


class _FakeRequest:
    def __init__(self, body, app):
        self._body = body
        self.app = app

    async def json(self):
        return self._body


class _FakeRequestError(Exception):
    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.code = code


class _FakeStreamResponse:
    def __init__(self):
        self.content_type = None
        self.headers = {}
        self.prepared = False
        self.writes: list[bytes] = []

    async def prepare(self, request):
        self.prepared = True
        return self

    async def write(self, data):
        self.writes.append(data if isinstance(data, bytes) else data.encode())


class _FakeUpstreamLines:
    def __init__(self, items, status_code=200):
        self._items = list(items)
        self.status_code = status_code

    async def aiter_lines(self):
        for item in self._items:
            if isinstance(item, Exception):
                raise item
            yield item


class _FakeUpstreamContent:
    def __init__(self, items, status_code=200):
        self._items = list(items)
        self.status_code = status_code

    async def aiter_content(self):
        for item in self._items:
            if isinstance(item, Exception):
                raise item
            yield item


class _FakeSession:
    def __init__(self, upstreams):
        self._upstreams = list(upstreams)
        self.calls = 0

    async def post(self, *args, **kwargs):
        upstream = self._upstreams[self.calls]
        self.calls += 1
        return upstream


async def _fake_credentials():
    return {"access_token": "test-token", "account_id": "acct_test"}


@pytest.mark.asyncio
async def test_handle_chat_completions_retries_before_first_downstream_byte(monkeypatch):
    first_error = _FakeRequestError(
        "Failed to perform, curl: (35) Recv failure: Connection reset by peer",
        35,
    )
    session = _FakeSession(
        [
            _FakeUpstreamLines([first_error]),
            _FakeUpstreamLines(
                [
                    'data: {"type":"response.output_item.added","item":{"type":"message","role":"assistant"}}',
                    'data: {"type":"response.output_text.delta","delta":"Hi"}',
                    (
                        'data: {"type":"response.completed","response":{"status":"completed",'
                        '"usage":{"input_tokens":1,"output_tokens":1,"total_tokens":2,'
                        '"input_tokens_details":{"cached_tokens":0}}}}'
                    ),
                ]
            ),
        ]
    )
    request = _FakeRequest(
        {
            "model": "gpt-5.1",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        },
        {"upstream_session": session},
    )

    monkeypatch.setattr("codex_proxy.server.ensure_credentials", _fake_credentials)
    monkeypatch.setattr("codex_proxy.server.web.StreamResponse", _FakeStreamResponse)

    response = await handle_chat_completions(request)

    assert isinstance(response, _FakeStreamResponse)
    assert session.calls == 2
    body = b"".join(response.writes).decode()
    assert '"content": "Hi"' in body
    assert body.count("data: [DONE]") == 1


@pytest.mark.asyncio
async def test_handle_responses_stream_writes_sse_error_after_upstream_reset(monkeypatch):
    stream_error = _FakeRequestError(
        "Failed to perform, curl: (35) Recv failure: Connection reset by peer",
        35,
    )
    session = _FakeSession(
        [
            _FakeUpstreamContent(
                [
                    b'data: {"type":"response.output_text.delta","delta":"hi"}\n\n',
                    stream_error,
                ]
            )
        ]
    )
    request = _FakeRequest(
        {
            "model": "gpt-5.3-codex",
            "input": "hi",
            "stream": True,
        },
        {"upstream_session": session},
    )

    monkeypatch.setattr("codex_proxy.server.ensure_credentials", _fake_credentials)
    monkeypatch.setattr("codex_proxy.server.web.StreamResponse", _FakeStreamResponse)

    response = await handle_responses(request)

    assert isinstance(response, _FakeStreamResponse)
    body = b"".join(response.writes).decode()
    assert '"type":"response.output_text.delta"' in body or '"type": "response.output_text.delta"' in body
    assert '"type": "error"' in body
    assert "connection_error" in body
    assert body.endswith("data: [DONE]\n\n")
