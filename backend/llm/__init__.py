"""LLM provider abstraction — a single client wrapper over OpenAI / Azure OpenAI."""

from llm.client import LLMClient, build_llm_client, get_llm_client

__all__ = ["LLMClient", "build_llm_client", "get_llm_client"]
