"""Thin wrappers over OpenAI-compatible endpoints (NVIDIA Build or a local server on the Spark)."""
import base64, json, re
from urllib.parse import urlparse
from openai import OpenAI
from . import config

BACKGROUND_TIMEOUT_S = 45     # digests, nightly report, title labels: may wait, must not hang
INTERACTIVE_TIMEOUT_S = 8     # someone is waiting on the reply (intent parsing, Ask)


def _client(base_url: str, timeout: float) -> OpenAI:
    # Retries would multiply the timeout; every caller has a rules fallback instead.
    return OpenAI(base_url=base_url, api_key=config.NVIDIA_API_KEY or "none", timeout=timeout, max_retries=0)


_text = _client(config.LLM_BASE_URL, BACKGROUND_TIMEOUT_S)
_text_fast = _client(config.LLM_BASE_URL, INTERACTIVE_TIMEOUT_S)
_vision = _client(config.VLM_BASE_URL, BACKGROUND_TIMEOUT_S)


def _is_nvidia(base_url: str) -> bool:
    host = (urlparse(base_url).hostname or "").lower()
    return host == "nvidia.com" or host.endswith(".nvidia.com")


def _extra(base_url: str) -> dict:
    """Thinking off for self-hosted Qwen3-style chat templates (vLLM/SGLang). NVIDIA Build rejects unknown kwargs."""
    return {} if _is_nvidia(base_url) else {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}


def _strip_think(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)   # reasoning models
    return re.sub(r"^.*?</think>", "", text, flags=re.S)                # opening tag eaten by the template


def _parse_json(text: str) -> dict:
    text = _strip_think(text)
    text = re.sub(r"```(?:json)?", "", text)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def chat_json(system: str, user: str, max_tokens: int = 500, interactive: bool = False) -> dict:
    r = (_text_fast if interactive else _text).chat.completions.create(
        model=config.LLM_MODEL, temperature=0, max_tokens=max_tokens,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        **_extra(config.LLM_BASE_URL),
    )
    return _parse_json(r.choices[0].message.content)


def chat_text(system: str, user: str, max_tokens: int = 600, interactive: bool = False) -> str:
    r = (_text_fast if interactive else _text).chat.completions.create(
        model=config.LLM_MODEL, temperature=0.3, max_tokens=max_tokens,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        **_extra(config.LLM_BASE_URL),
    )
    return _strip_think(r.choices[0].message.content).strip()


def vision_json(system: str, prompt: str, jpeg: bytes, max_tokens: int = 200) -> dict:
    b64 = base64.b64encode(jpeg).decode()
    r = _vision.chat.completions.create(
        model=config.VLM_MODEL, temperature=0, max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ]},
        ],
        **_extra(config.VLM_BASE_URL),
    )
    return _parse_json(r.choices[0].message.content)
