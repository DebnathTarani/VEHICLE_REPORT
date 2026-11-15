import base64

import httpx

from app.config import get_settings
from app.services.providers.base import ExtractionError, ProviderSpec


async def list_models(spec: ProviderSpec) -> list[str]:
    url = f"{spec.openai_base()}/v1/models"
    async with httpx.AsyncClient(timeout=15) as client:
        headers = {}
        if spec.api_key:
            headers["Authorization"] = f"Bearer {spec.api_key}"
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    out: list[str] = []
    for item in data.get("data", []):
        if isinstance(item, dict) and item.get("id"):
            out.append(str(item["id"]))
        elif isinstance(item, str):
            out.append(item)
    return out


def _body(spec: ProviderSpec, content: list | str) -> dict:
    body: dict = {
        "model": spec.model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0,
        "max_tokens": 4096,
    }
    if spec.disable_thinking:
        body["chat_template_kwargs"] = {"enable_thinking": False}
    return body


async def chat_with_image(
    spec: ProviderSpec,
    prompt: str,
    image_data: bytes,
    mime: str,
    guided_json: dict | None = None,
) -> str:
    data_uri = f"data:{mime};base64,{base64.b64encode(image_data).decode()}"
    content = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": data_uri}},
    ]
    body = _body(spec, content)
    if guided_json and spec.supports_guided_json:
        body["guided_json"] = guided_json
    headers = {"Content-Type": "application/json"}
    if spec.api_key:
        headers["Authorization"] = f"Bearer {spec.api_key}"
    timeout = spec.timeout or get_settings().llm_timeout_seconds
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{spec.openai_base()}/v1/chat/completions", json=body, headers=headers
        )
    if resp.status_code != 200:
        raise ExtractionError(f"provider error {resp.status_code}: {resp.text[:500]}")
    payload = resp.json()
    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ExtractionError(f"malformed provider response: {exc}") from exc


async def list_models_openai(spec: ProviderSpec) -> list[str]:  # alias
    return await list_models(spec)
