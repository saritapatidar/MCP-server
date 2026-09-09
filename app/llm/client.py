"""
LLM provider client.

This module defines a provider-independent interface for calling an LLM
to review code.

The review pipeline depends only on the LLMClient interface, so different
providers such as Claude and Ollama can be used without changing the
review pipeline.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMClient(ABC):
    """Provider-independent interface for a single-turn LLM call."""

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """
        Send a prompt to the LLM and return its raw text response.

        Args:
            system_prompt: Instructions that define the LLM's role,
                output format, and review standards.
            user_prompt: The code context to review.

        Returns:
            The raw text of the LLM's response.

        Raises:
            LLMClientError: If the provider call fails.
        """


class LLMClientError(Exception):
    """Raised when an LLM provider call fails or is misconfigured."""


class ClaudeClient(LLMClient):
    """LLMClient implementation backed by the Anthropic Claude API."""

    DEFAULT_MODEL = "claude-sonnet-4-6"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        """
        Create a Claude-backed LLM client.

        Args:
            api_key: Anthropic API key. Falls back to the
                ANTHROPIC_API_KEY environment variable.
            model: Claude model name. Falls back to the
                ANTHROPIC_MODEL environment variable, then
                DEFAULT_MODEL.

        Raises:
            LLMClientError: If no API key is available or the
                anthropic package is not installed.
        """
        resolved_key = api_key or os.getenv("ANTHROPIC_API_KEY")

        if not resolved_key:
            raise LLMClientError(
                "ANTHROPIC_API_KEY is not configured. "
                "Please add it to the .env file."
            )

        try:
            import anthropic
        except ImportError as exc:
            raise LLMClientError(
                "The 'anthropic' package is required to use ClaudeClient. "
                "Install it with: pip install anthropic"
            ) from exc

        self._client = anthropic.Anthropic(api_key=resolved_key)
        self._model = model or os.getenv(
            "ANTHROPIC_MODEL",
            self.DEFAULT_MODEL,
        )

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """
        Send a prompt to Claude and return its raw text response.
        """
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_prompt,
                    }
                ],
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Claude API call failed: %s", exc)
            raise LLMClientError(
                f"Claude API call failed: {exc}"
            ) from exc

        text_blocks = [
            block.text
            for block in response.content
            if block.type == "text"
        ]

        return "".join(text_blocks)


class OllamaClient(LLMClient):
    """LLMClient implementation backed by a local Ollama server."""

    DEFAULT_BASE_URL = "http://127.0.0.1:11434"
    DEFAULT_MODEL = "llama3:8b"

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        """
        Create an Ollama-backed LLM client.

        Args:
            base_url: Ollama server URL. Falls back to the
                OLLAMA_BASE_URL environment variable, then
                DEFAULT_BASE_URL.
            model: Ollama model name. Falls back to the
                OLLAMA_MODEL environment variable, then
                DEFAULT_MODEL.

        Raises:
            LLMClientError: If the Ollama client dependency
                is not installed.
        """
        self._base_url = (
            base_url
            or os.getenv(
                "OLLAMA_BASE_URL",
                self.DEFAULT_BASE_URL,
            )
        ).rstrip("/")

        self._model = model or os.getenv(
            "OLLAMA_MODEL",
            self.DEFAULT_MODEL,
        )
        self._timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "300"))

        try:
            import httpx
        except ImportError as exc:
            raise LLMClientError(
                "The 'httpx' package is required to use OllamaClient. "
                "Install it with: pip install httpx"
            ) from exc

        self._httpx = httpx

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """
        Send a prompt to Ollama and return its raw text response.
        """

        url = f"{self._base_url}/api/chat"

        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            "stream": False,
            "options":{"num_predict": 1800,"num_ctx": 8192,"temperature": 0.2,},
        }

        try:
            response = self._httpx.post(
                url,
                json=payload,
                timeout=self._timeout,
            )

            response.raise_for_status()

        except Exception as exc:  # noqa: BLE001
            logger.error("Ollama API call failed: %s", exc)

            raise LLMClientError(
                f"Ollama API call failed: {exc}"
            ) from exc

        try:
            data = response.json()
            return data["message"]["content"]

        except (KeyError, TypeError, ValueError) as exc:
            logger.error(
                "Unexpected response received from Ollama: %s",
                response.text,
            )

            raise LLMClientError(
                "Ollama returned an unexpected response format."
            ) from exc


def get_llm_client(provider: str | None = None) -> LLMClient:
    """
    Create an LLM client for the configured provider.

    Args:
        provider: Provider name ("claude" or "ollama").
            Falls back to the LLM_PROVIDER environment variable,
            then "ollama".

    Returns:
        A configured LLMClient.

    Raises:
        LLMClientError: If the provider is unknown.
    """

    resolved_provider = (
        provider
        or os.getenv("LLM_PROVIDER", "ollama")
    ).lower()

    if resolved_provider == "claude":
        return ClaudeClient()

    if resolved_provider == "ollama":
        return OllamaClient()

    raise LLMClientError(
        f"Unsupported LLM provider: '{resolved_provider}'. "
        "Supported providers are: claude, ollama."
    )
