import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx2 as httpx
import pytest

from competitor_pulse.poller.llm_client import (
    LLMConnectionError,
    LLMHTTPError,
    LLMTimeoutError,
    LLMUnusableAnswerError,
    OpenAILLMClient,
)

pytestmark = pytest.mark.anyio

TIMEOUT_SECONDS = 30
MAX_TOKENS = 150
MAX_ANSWER_CHARS = 300


def completion(content: Any, finish_reason: str = "stop") -> dict:
    return {
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            }
        ],
    }


def client(handler: Callable[[httpx.Request], httpx.Response]) -> OpenAILLMClient:
    http = httpx.AsyncClient(base_url="http://llm.test/v1/", transport=httpx.MockTransport(handler))
    return OpenAILLMClient(http, "mock-llm", TIMEOUT_SECONDS, MAX_TOKENS, MAX_ANSWER_CHARS)


def answer(response: httpx.Response) -> OpenAILLMClient:
    return client(lambda _request: response)


def fail_with(error: Exception) -> OpenAILLMClient:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    return client(handler)


async def test_asks_the_chat_completions_api_and_returns_the_answer():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=completion("  Price dropped to $29/mo.\n"))

    summary = await client(handler).complete("Summarize.", "price: $39/mo -> $29/mo")

    assert summary == "Price dropped to $29/mo."
    [request] = requests
    assert (request.method, str(request.url)) == ("POST", "http://llm.test/v1/chat/completions")
    assert json.loads(request.content) == {
        "model": "mock-llm",
        "messages": [
            {"role": "system", "content": "Summarize."},
            {"role": "user", "content": "price: $39/mo -> $29/mo"},
        ],
        "temperature": 0,
        "max_tokens": MAX_TOKENS,
    }


@pytest.mark.parametrize("status", [500, 503, 401, 404])
async def test_http_error(status: int):
    with pytest.raises(LLMHTTPError) as err:
        await answer(httpx.Response(status, json={"error": {"message": "nope"}})).complete("", "")

    assert err.value.status == status


async def test_timeout():
    with pytest.raises(LLMTimeoutError) as err:
        await fail_with(httpx.ReadTimeout("no answer")).complete("", "")

    assert err.value.after_seconds == TIMEOUT_SECONDS


async def test_timeout_bounds_the_whole_call():
    # Each chunk arrives quickly, so no single read times out, but the whole answer is late.
    async def slow_body() -> AsyncIterator[bytes]:
        for _ in range(10):
            await asyncio.sleep(0.02)
            yield b" "

    http = httpx.AsyncClient(
        base_url="http://llm.test/v1/",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, content=slow_body())),
    )
    llm = OpenAILLMClient(http, "mock-llm", 0.05, MAX_TOKENS, MAX_ANSWER_CHARS)

    with pytest.raises(LLMTimeoutError) as err:
        await llm.complete("", "")

    assert err.value.after_seconds == 0.05


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectError("connection refused"),
        httpx.RemoteProtocolError("connection closed"),
        httpx.DecodingError("invalid gzip data"),
    ],
)
async def test_connection_error(error: Exception):
    with pytest.raises(LLMConnectionError):
        await fail_with(error).complete("", "")


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="<html>not json</html>"),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"choices": [{"message": {}}]}),
        httpx.Response(200, json=completion(None)),
        httpx.Response(200, json=completion(["a", "list"])),
        httpx.Response(200, json=completion("   ")),
        httpx.Response(200, json=completion("Price dropped", finish_reason="length")),
        httpx.Response(200, json=completion("x" * (MAX_ANSWER_CHARS + 1))),
        # Not one plain-text paragraph: the model did not do what it was asked.
        httpx.Response(200, json=completion("Price dropped.\nAlso: buy now.")),
        httpx.Response(200, json=completion("Details at https://acme.example/deal")),
        httpx.Response(200, json=completion("Details at www.acme.example")),
        httpx.Response(200, json=completion("Price **dropped** to $29/mo.")),
        httpx.Response(200, json=completion("- Price dropped to $29/mo")),
        httpx.Response(200, json=completion("Price <b>dropped</b> to $29/mo.")),
        httpx.Response(
            200, json=completion("<listing_change> Price <b>dropped</b>. </listing_change>")
        ),
        httpx.Response(200, json=completion("See [the deal](https://acme.example).")),
    ],
)
async def test_unusable_answer(response: httpx.Response):
    with pytest.raises(LLMUnusableAnswerError):
        await answer(response).complete("", "")


@pytest.mark.parametrize(
    "summary",
    [
        "The price dropped from $39/mo to $29/mo.",
        'The tagline changed to "Docs <3 teams", and the price is now free.',
        "The price fell 25% - from $39/mo to $29/mo.",
        # The mock LLM echoes the prompt, markers and all.
        'Mock AI summary (not a real model). Based on what you sent: "<listing_change> {'
        ' "competitor": "acme-crm" } </listing_change>"',
    ],
)
async def test_plain_summaries_are_accepted(summary: str):
    assert await answer(httpx.Response(200, json=completion(summary))).complete("", "") == summary
