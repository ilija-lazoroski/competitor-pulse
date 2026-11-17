from typing import Protocol


class LlmClient(Protocol):
    """Asks an LLM for a short text."""

    async def complete(self, instructions: str, prompt: str) -> str:
        """Asks the LLM to answer a prompt, following the instructions.

        :param instructions: What the LLM is asked to do, sent as the system message
        :param prompt: The text to answer, sent as the user message
        :returns: The answer, without surrounding whitespace
        :raises LlmTimeoutError: If the LLM does not answer in time
        :raises LlmConnectionError: If the LLM cannot be reached or the request fails
        :raises LlmHttpError: If the LLM answers with an HTTP error status
        :raises LlmUnusableAnswerError: If the answer is missing, empty, cut off, too long, or
                                        not one plain-text paragraph
        """
        ...
