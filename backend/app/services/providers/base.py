from dataclasses import dataclass

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_GEMINI_BASE = "https://generativelanguage.googleapis.com"


class ExtractionError(Exception):
    pass


@dataclass
class ProviderSpec:
    kind: str  # openai | gemini
    base_url: str | None
    api_key: str | None
    model: str
    supports_guided_json: bool = True
    disable_thinking: bool = False
    timeout: float = 180.0

    def openai_base(self) -> str:
        base = (self.base_url or "http://localhost:8000").rstrip("/")
        if not base.startswith("http"):
            base = "http://" + base
        return base


def image_mime(data: bytes) -> str:
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:2] == b"BM":
        return "image/bmp"
    return "image/jpeg"


def gemini_schema(schema: dict) -> dict:
    """Convert our constrained JSON schema subset to Gemini's OpenAPI-like schema."""
    t = schema.get("type")
    out: dict = {}
    type_map = {
        "object": "OBJECT",
        "array": "ARRAY",
        "string": "STRING",
        "number": "NUMBER",
        "integer": "INTEGER",
        "boolean": "BOOLEAN",
    }
    if t in type_map:
        out["type"] = type_map[t]
    if t == "object":
        props = {}
        for key, sub in (schema.get("properties") or {}).items():
            props[key] = gemini_schema(sub)
        out["properties"] = props
        if schema.get("required"):
            out["required"] = list(schema["required"])
        out["propertyOrdering"] = list(props.keys())
    elif t == "array":
        out["items"] = gemini_schema(schema.get("items", {"type": "string"}))
    if "enum" in schema:
        out["enum"] = list(schema["enum"])
    return out
