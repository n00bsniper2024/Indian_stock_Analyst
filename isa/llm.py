"""Provider-agnostic LLM client.

Every provider except Anthropic speaks the OpenAI Chat Completions protocol, so one code path
covers DeepSeek, OpenAI, Gemini, Groq, OpenRouter, Ollama and any custom endpoint.
Model names change often, so the UI lists models live from each provider's /models endpoint;
`preferred` only decides which one is pre-selected.
API keys are passed per call and never written to disk or logs by this module.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Iterator


@dataclass(frozen=True)
class Provider:
    name: str
    kind: str  # "openai" | "anthropic"
    base_url: str | None
    env_key: str | None
    preferred: tuple[str, ...] = field(default_factory=tuple)
    key_url: str = ""
    note: str = ""


PROVIDERS: dict[str, Provider] = {
    p.name: p
    for p in [
        Provider("DeepSeek", "openai", "https://api.deepseek.com", "DEEPSEEK_API_KEY",
                 ("deepseek-flash", "deepseek-v4-pro", "deepseek-v4-flash", "deepseek-chat"),
                 "https://platform.deepseek.com/api_keys", "Cheapest capable option. Data is processed on DeepSeek servers (China)."),
        Provider("Google Gemini", "openai", "https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY",
                 ("gemini-3.8-flash", "flash", "pro"), "https://aistudio.google.com/apikey", "Has a free tier (rate-limited)."),
        Provider("OpenAI", "openai", None, "OPENAI_API_KEY", ("mini", "gpt-5", "gpt-4.1"), "https://platform.openai.com/api-keys"),
        Provider("Anthropic Claude", "anthropic", None, "ANTHROPIC_API_KEY",
                 ("claude-sonnet-5-5", "sonnet", "haiku", "opus"), "https://console.anthropic.com/settings/keys",
                 "Strongest at careful financial reasoning; higher cost."),
        Provider("Groq", "openai", "https://api.groq.com/openai/v1", "GROQ_API_KEY", ("llama", "qwen", "gpt-oss"),
                 "https://console.groq.com/keys", "Very fast; free tier."),
        Provider("OpenRouter", "openai", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY",
                 ("deepseek/deepseek-v4", "deepseek", "anthropic/claude", "google/gemini"), "https://openrouter.ai/keys",
                 "One key, hundreds of models."),
        Provider("Ollama (local, free)", "openai", "http://localhost:11434/v1", None, ("qwen", "llama", "deepseek"),
                 "https://ollama.com/download", "Runs on your machine; no key, no data leaves your PC. Quality depends on model size."),
        Provider("Custom (OpenAI-compatible)", "openai", "", "CUSTOM_LLM_API_KEY", (), ""),
    ]
}


class LLMError(RuntimeError):
    pass


def default_key(provider: str) -> str:
    p = PROVIDERS[provider]
    if not p.env_key:
        return ""
    val = os.getenv(p.env_key, "")
    if not val:
        try:  # Streamlit Cloud secrets
            import streamlit as st

            val = st.secrets.get(p.env_key, "")  # type: ignore[attr-defined]
        except Exception:
            val = ""
    return val


def _openai_client(p: Provider, api_key: str, base_url: str | None):
    from openai import OpenAI

    url = base_url if base_url else p.base_url
    return OpenAI(api_key=api_key or "not-needed", base_url=url or None, timeout=180, max_retries=2)


def list_models(provider: str, api_key: str, base_url: str | None = None) -> list[str]:
    p = PROVIDERS[provider]
    try:
        if p.kind == "anthropic":
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
            ids = [m.id for m in client.models.list(limit=100)]
        else:
            ids = [m.id.removeprefix("models/") for m in _openai_client(p, api_key, base_url).models.list()]
    except Exception as exc:
        raise LLMError(f"Could not list models for {provider}: {_short(exc)}") from exc
    skip = ("embed", "tts", "whisper", "image", "audio", "dall", "moderation", "realtime", "transcribe", "veo", "imagen")
    ids = sorted({i for i in ids if not any(s in i.lower() for s in skip)})
    return sorted(ids, key=lambda m: _pref_rank(p, m))


def _pref_rank(p: Provider, model: str) -> tuple[int, str]:
    for i, pref in enumerate(p.preferred):
        if pref.lower() in model.lower():
            return (i, model)
    return (len(p.preferred), model)


def _short(exc: Exception) -> str:
    msg = str(exc)
    msg = re.sub(r"(sk|key)-[A-Za-z0-9_\-]{8,}", "[redacted]", msg)  # never echo keys
    return msg[:400]


def chat(provider: str, api_key: str, model: str, messages: list[dict[str, str]], *, json_mode: bool = False,
         temperature: float = 0.2, max_tokens: int = 6000, base_url: str | None = None) -> str:
    p = PROVIDERS[provider]
    if p.env_key and not api_key and p.name != "Custom (OpenAI-compatible)":
        raise LLMError(f"No API key for {provider}. Paste one in the sidebar or set {p.env_key} in .env.")
    try:
        if p.kind == "anthropic":
            import anthropic

            client = anthropic.Anthropic(api_key=api_key, timeout=240)
            system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
            convo = [m for m in messages if m["role"] != "system"]
            if json_mode:  # newer Claude models don't allow assistant prefill; ask explicitly instead
                system += "\n\nRespond with a single valid JSON object only — no prose, no code fences."
            r = client.messages.create(model=model, system=system, messages=convo, max_tokens=max_tokens, temperature=temperature)
            return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        client = _openai_client(p, api_key, base_url)
        kwargs: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            r = client.chat.completions.create(**kwargs)
        except Exception as exc:  # some models reject response_format / temperature — retry plainly
            if any(s in str(exc).lower() for s in ("response_format", "temperature", "unsupported", "max_tokens")):
                kwargs.pop("response_format", None)
                kwargs.pop("temperature", None)
                kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
                r = client.chat.completions.create(**kwargs)
            else:
                raise
        return r.choices[0].message.content or ""
    except LLMError:
        raise
    except Exception as exc:
        raise LLMError(f"{provider} request failed: {_short(exc)}") from exc


def stream_chat(provider: str, api_key: str, model: str, messages: list[dict[str, str]], *, temperature: float = 0.3,
                max_tokens: int = 2500, base_url: str | None = None) -> Iterator[str]:
    p = PROVIDERS[provider]
    try:
        if p.kind == "anthropic":
            import anthropic

            client = anthropic.Anthropic(api_key=api_key, timeout=240)
            system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
            convo = [m for m in messages if m["role"] != "system"]
            with client.messages.stream(model=model, system=system, messages=convo, max_tokens=max_tokens, temperature=temperature) as s:
                yield from s.text_stream
            return
        client = _openai_client(p, api_key, base_url)
        stream = client.chat.completions.create(model=model, messages=messages, temperature=temperature,
                                                max_tokens=max_tokens, stream=True)
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as exc:
        raise LLMError(f"{provider} request failed: {_short(exc)}") from exc


def parse_json(text: str) -> dict[str, Any]:
    """Tolerant JSON extraction: strips <think> blocks and ``` fences, then takes the outermost object."""
    t = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    t = re.sub(r"^```(?:json)?|```$", "", t.strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        start, end = t.find("{"), t.rfind("}")
        if start >= 0 and end > start:
            return json.loads(t[start : end + 1])
        raise
