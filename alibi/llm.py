"""Thin wrappers over OpenAI-compatible endpoints (NVIDIA Build or a local server on the Spark)."""
import base64, json, re
from openai import OpenAI
from . import config

_text = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.NVIDIA_API_KEY or "none")
_vision = OpenAI(base_url=config.VLM_BASE_URL, api_key=config.NVIDIA_API_KEY or "none")


def _parse_json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)   # reasoning models
    text = re.sub(r"```(?:json)?", "", text)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def chat_json(system: str, user: str, max_tokens: int = 500) -> dict:
    r = _text.chat.completions.create(
        model=config.LLM_MODEL, temperature=0, max_tokens=max_tokens,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return _parse_json(r.choices[0].message.content)


def chat_text(system: str, user: str, max_tokens: int = 300) -> str:
    r = _text.chat.completions.create(
        model=config.LLM_MODEL, temperature=0.3, max_tokens=max_tokens,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return re.sub(r"<think>.*?</think>", "", r.choices[0].message.content or "", flags=re.S).strip()


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
    )
    return _parse_json(r.choices[0].message.content)
