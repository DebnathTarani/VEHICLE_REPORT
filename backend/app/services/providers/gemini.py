import base64

import httpx

from app.config import get_settings
from app.services.providers.base import (
    DEFAULT_GEMINI_BASE,
    DEFAULT_GEMINI_MODEL,
    ExtractionError,
    ProviderSpec,
    gemini_schema,
)


def _base(spec: ProviderSpec) -> str:
    return (spec.base_url or DEFAULT_GEMINI_BASE).rstrip("/")


def _model(spec: ProviderSpec) -> str:
    return spec.model or DEFAULT_GEMINI_MODEL


async def list_models(spec: ProviderSpec) -> list[str]:
    url = f"{_base(spec)}/v1beta/models"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params={"key": spec.api_key or ""})
        resp.raise_for_status()
        data = resp.json()
    return [m.get("name", "").removeprefix("models/") for m in data.get("models", []) if m.get("name")]


async def chat_with_image(
    spec: ProviderSpec,
    prompt: str,
    image_data: bytes,
    mime: str,
    guided_json: dict | None = None,
) -> str:
    body: dict = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": mime,
                            "data": base64.b64encode(image_data).decode(),
                        }
                    },
                ]
            }
        ],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 4096},
    }
    if guided_json:
        body["generationConfig"]["responseMimeType"] = "application/json"
        body["generationConfig"]["responseSchema"] = gemini_schema(guided_json)
    url = f"{_base(spec)}/v1beta/models/{_model(spec)}:generateContent"
    timeout = spec.timeout or get_settings().llm_timeout_seconds
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, params={"key": spec.api_key or ""}, json=body)
    if resp.status_code != 200:
        raise ExtractionError(f"gemini error {resp.status_code}: {resp.text[:500]}")
    payload = resp.json()
    try:
        parts = payload["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
    except (KeyError, IndexError, TypeError) as exc:
        raise ExtractionError(f"malformed gemini response: {exc}") from exc
