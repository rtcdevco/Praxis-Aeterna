"""A minimal Anthropic client test double — no network calls.

Used by tests that need to inject `anthropic_client=...` into `create_app()`
without hitting the real API.
"""

from __future__ import annotations

from types import SimpleNamespace


class FakeMessages:
    def __init__(self, create_results=None, count_tokens_fn=None):
        self.calls: list[dict] = []
        self.count_token_calls: list[dict] = []
        self._create_results = list(create_results or [])
        self._count_tokens_fn = count_tokens_fn or (lambda text: len(text) // 4 + 1)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        result = self._create_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def count_tokens(self, **kwargs):
        self.count_token_calls.append(kwargs)
        text = kwargs["messages"][0]["content"]
        return SimpleNamespace(input_tokens=self._count_tokens_fn(text))


class FakeAnthropicClient:
    def __init__(self, create_results=None, count_tokens_fn=None):
        self.messages = FakeMessages(create_results, count_tokens_fn)


def fake_message(
    text: str,
    model: str = "claude-haiku-4-5",
    stop_reason: str = "end_turn",
    input_tokens: int = 10,
    output_tokens: int = 5,
):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        model=model,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )
