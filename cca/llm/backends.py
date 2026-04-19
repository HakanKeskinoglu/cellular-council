# Copyright 2026 Hakan (CCA Framework Contributors)
# SPDX-License-Identifier: Apache-2.0

"""
LLM Backends for CCA.

Cells are LLM-agnostic — any backend implementing BaseLLMBackend can power them.
This makes CCA deployable in air-gapped environments (Ollama), cloud (OpenAI/Anthropic),
or hybrid configurations.

    ┌────────────────────────────────────────────┐
    │            BaseLLMBackend                  │
    │                                            │
    │   complete(system, user) → str             │
    └──────────┬───────────────┬─────────────────┘
               │               │
     ┌─────────▼────┐   ┌──────▼──────────┐
     │ OllamaBackend│   │ OpenAIBackend   │
     │ (local/airgap│   │ (cloud)         │
     └─────────────-┘   └─────────────────┘
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import httpx
import structlog

logger = structlog.get_logger(__name__)


class BaseLLMBackend(ABC):
    """Abstract base class for all LLM backends."""

    @abstractmethod
    async def complete(self, system: str, user: str) -> str:
        """
        Generate a completion from the LLM.

        Parameters
        ----------
        system : str
            System prompt (cell specialization instructions).
        user : str
            User message (query + context).

        Returns
        -------
        str
            Raw text response from the model.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the backend is reachable and operational."""
        ...


class OllamaBackend(BaseLLMBackend):
    """
    Ollama local LLM backend.

    Ideal for air-gapped environments like data centers where external API
    calls are not permitted. Supports any model available in Ollama.

    Parameters
    ----------
    model : str
        Ollama model name (e.g., "llama3.2", "mistral", "qwen2.5").
    base_url : str
        Ollama API URL. Default: http://localhost:11434
    temperature : float
        Sampling temperature (0.0 = deterministic, 1.0 = creative).
    timeout : float
        Request timeout in seconds.
    num_ctx : int
        Context window size in tokens.

    Examples
    --------
    >>> backend = OllamaBackend(model="llama3.2", temperature=0.3)
    >>> response = await backend.complete(system="You are a risk analyst.", user="Assess this alarm.")
    """

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.3,
        timeout: float = 120.0,
        num_ctx: int = 4096,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.timeout = timeout
        self.num_ctx = num_ctx
        self._client = httpx.AsyncClient(timeout=timeout)

    async def complete(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
            },
        }

        response = await self._client.post(
            f"{self.base_url}/api/chat",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get(f"{self.base_url}/api/tags", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """Return list of locally available Ollama models."""
        resp = await self._client.get(f"{self.base_url}/api/tags")
        resp.raise_for_status()
        data = resp.json()
        return [m["name"] for m in data.get("models", [])]

    def __repr__(self) -> str:
        return f"OllamaBackend(model={self.model!r}, url={self.base_url!r})"


class OpenAIBackend(BaseLLMBackend):
    """
    OpenAI-compatible backend (works with OpenAI API and any compatible server).

    Parameters
    ----------
    model : str
        Model identifier (e.g., "gpt-4o", "gpt-4o-mini").
    api_key : str
        OpenAI API key.
    base_url : str, optional
        Override for OpenAI-compatible servers (e.g., Together AI, Groq).
    temperature : float
        Sampling temperature.
    max_tokens : int
        Maximum tokens in response.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> None:
        import os
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=60.0,
        )

    async def complete(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        response = await self._client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get(f"{self.base_url}/models", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    def __repr__(self) -> str:
        return f"OpenAIBackend(model={self.model!r})"


class AnthropicBackend(BaseLLMBackend):
    """
    Anthropic Claude backend.

    Parameters
    ----------
    model : str
        Claude model identifier.
    api_key : str, optional
        Anthropic API key. Falls back to ANTHROPIC_API_KEY env var.
    """

    def __init__(
        self,
        model: str = "claude-3-haiku-20240307",
        api_key: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> None:
        import os
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = httpx.AsyncClient(
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            timeout=60.0,
        )

    async def complete(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }

        response = await self._client.post(
            "https://api.anthropic.com/v1/messages",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"]

    async def health_check(self) -> bool:
        return bool(self.api_key)

    def __repr__(self) -> str:
        return f"AnthropicBackend(model={self.model!r})"
