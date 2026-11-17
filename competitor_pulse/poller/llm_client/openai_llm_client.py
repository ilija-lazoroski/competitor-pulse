import re
from http import HTTPStatus
from typing import Any, Final

import httpx2 as httpx

from competitor_pulse.configuration import LlmConfiguration
from competitor_pulse.poller.llm_client.errors import (
    LlmConnectionError,
    LlmHttpError,
    LlmTimeoutError,
    LlmUnusableAnswerError,
)
from competitor_pulse.poller.llm_client.llm_client import LlmClient

# A summary is shown as plain text: links and markup in an answer mean the model did not do
# what it was asked, possibly because the listing it was given tried to instruct it.
_LINK: Final = re.compile(r"https?://|www\.", re.IGNORECASE)
_MARKUP: Final = re.compile(
    r"<[a-z/!][^>]*>"  # HTML tags
    r"|```"  # code blocks
    r"|\*\*|__"  # bold
    r"|\[[^\]]*\]\([^)]*\)"  # Markdown links
    r"|^\s*(?:#{1,6}\s|[-*+]\s|\d+\.\s)",  # headings and list items
    re.IGNORECASE | re.MULTILINE,
)


class OpenAiLlmClient(LlmClient):
    """The LlmClient for an OpenAI-compatible Chat Completions API: the mock, Ollama and others.

    It makes one request per call and never retries; the summarizer decides about retries,
    because every call counts against the daily cap.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        model: str,
        timeout_seconds: float,
        max_tokens: int,
        max_answer_chars: int,
    ):
        self._client = client
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_tokens = max_tokens
        self._max_answer_chars = max_answer_chars

    @classmethod
    def from_configuration(cls, config: LlmConfiguration) -> "OpenAiLlmClient":
        """Creates the client with its own HTTP client; close() closes it.

        :param config: The LLM settings
        :returns: The client, ready to call the LLM
        """
        headers = {}
        if config.api_key is not None:
            headers["Authorization"] = f"Bearer {config.api_key.get_secret_value()}"
        client = httpx.AsyncClient(
            base_url=str(config.base_url).rstrip("/") + "/",
            headers=headers,
            timeout=config.timeout_seconds,
        )
        return cls(
            client,
            config.model,
            config.timeout_seconds,
            config.max_tokens,
            config.max_summary_chars,
        )

    async def complete(self, instructions: str, prompt: str) -> str:
        """Asks the LLM to answer a prompt, following the instructions.

        :param instructions: What the LLM is asked to do, sent as the system message
        :param prompt: The text to answer, sent as the user message
        :returns: The answer, without surrounding whitespace
        :raises LlmTimeoutError: If the LLM does not answer in time
        :raises LlmConnectionError: If the LLM cannot be reached
        :raises LlmHttpError: If the LLM answers with an HTTP error status
        :raises LlmUnusableAnswerError: If the answer is missing, empty, cut off, too long, or
                                        not one plain-text paragraph
        """
        request = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": prompt},
            ],
            # Deterministic and short: no room for creativity or long detours.
            "temperature": 0,
            "max_tokens": self._max_tokens,
        }
        try:
            response = await self._client.post("chat/completions", json=request)
        except httpx.TimeoutException as err:
            raise LlmTimeoutError(self._timeout_seconds) from err
        except httpx.TransportError as err:
            raise LlmConnectionError(str(err) or type(err).__name__) from err

        if response.status_code != HTTPStatus.OK:
            raise LlmHttpError(response.status_code)
        return self._answer(response)

    async def close(self) -> None:
        """Closes the HTTP client and its connections."""
        await self._client.aclose()

    def _answer(self, response: httpx.Response) -> str:
        """Reads the answer out of a Chat Completions response and checks it can be shown.

        :param response: The LLM's 200 response
        :returns: The answer, without surrounding whitespace
        :raises LlmUnusableAnswerError: If the answer is missing, empty, cut off, too long, or
                                        not one plain-text paragraph
        """
        try:
            choice: dict[str, Any] = response.json()["choices"][0]
            content = choice["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as err:
            raise LlmUnusableAnswerError("not a Chat Completions response") from err

        if not isinstance(content, str) or not content.strip():
            raise LlmUnusableAnswerError("the answer is empty")
        if choice.get("finish_reason") == "length":
            raise LlmUnusableAnswerError("the answer was cut off")
        answer = content.strip()
        if len(answer) > self._max_answer_chars:
            raise LlmUnusableAnswerError(
                f"the answer is longer than {self._max_answer_chars} characters"
            )
        if "\n" in answer:
            raise LlmUnusableAnswerError("the answer has more than one line")
        if _LINK.search(answer):
            raise LlmUnusableAnswerError("the answer contains a link")
        if _MARKUP.search(answer):
            raise LlmUnusableAnswerError("the answer contains Markdown or HTML")
        return answer
