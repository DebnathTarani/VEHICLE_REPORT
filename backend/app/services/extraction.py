import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from app.config import get_settings
from app.models import LlmProvider
from app.security import decrypt_secret
from app.services import ocr as ocr_service
from app.services.dates import fmt_date, fmt_time, parse_date_loose, parse_time_loose
from app.services.image_prep import preprocess_image
from app.services.providers import gemini as gemini_client
from app.services.providers import openai_compat as openai_client
from app.services.providers.base import ExtractionError, ProviderSpec, image_mime
from app.services.vrn import is_valid_vrn, normalize_vrn

PROMPT_VERSION = "v1"
_PROMPT_PATH = Path(__file__).resolve().parent.parent / "ml_assets" / "prompt_v1.md"

_STATUS_MAP = [
    (("cancel",), "cancelled"),
    (("done", "complete", "exit", "out"), "work_done"),
    (("progress", "wip"), "in_progress"),
    (("pending", "wait"), "pending"),
]

EXTRACTION_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sr_no": {"type": "string"},
                    "vrn": {"type": "string"},
                    "model": {"type": "string"},
                    "entry_date": {"type": "string"},
                    "in_time": {"type": "string"},
                    "out_date": {"type": "string"},
                    "out_time": {"type": "string"},
                    "status": {"type": "string", "enum": ["work_done", "in_progress", "pending", "cancelled"]},
                    "remarks": {"type": "string"},
                    "confidence": {
                        "type": "object",
                        "properties": {
                            "vrn": {"type": "number"},
                            "model": {"type": "number"},
                            "entry_date": {"type": "number"},
                            "in_time": {"type": "number"},
                            "out_date": {"type": "number"},
                            "out_time": {"type": "number"},
                            "status": {"type": "number"},
                        },
                    },
                },
                "required": ["vrn", "entry_date"],
            },
        }
    },
    "required": ["rows"],
}

_FIELDS = ("vrn", "model", "entry_date", "in_time", "out_date", "out_time", "status")


@dataclass
class ExtractionResult:
    rows: list[dict] = field(default_factory=list)
    confidences: list[dict | None] = field(default_factory=list)
    provider: str = ""
    model: str = ""
    ocr_available: bool = False
    raw_response: str | None = None


def build_prompt(ocr_text: str | None, today: date | None = None) -> str:
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    today = today or date.today()
    ocr_section = ""
    if ocr_text:
        ocr_section = (
            "OCR text read from the image (use ONLY to verify your character-level reading "
            "of VRNs, dates and times; it may contain noise):\n---\n"
            + ocr_text
            + "\n---\n"
        )
    return template.format(
        date_context=today.isoformat() + f" ({today.strftime('%d-%m-%Y')})",
        ocr_section=ocr_section,
    )


def provider_spec(p: LlmProvider) -> ProviderSpec:
    return ProviderSpec(
        kind=p.kind,
        base_url=p.base_url,
        api_key=decrypt_secret(p.api_key_enc),
        model=p.default_model,
        supports_guided_json=p.supports_guided_json,
        disable_thinking=p.disable_thinking,
        timeout=float(get_settings().llm_timeout_seconds),
    )


async def call_provider(spec: ProviderSpec, prompt: str, image_bytes: bytes, guided: bool) -> str:
    mime = image_mime(image_bytes)
    client = gemini_client if spec.kind == "gemini" else openai_client
    return await client.chat_with_image(
        spec, prompt, image_bytes, mime, EXTRACTION_SCHEMA if guided else None
    )


def parse_extraction_response(text: str) -> list[dict]:
    """Tolerant JSON extraction (guided decoding makes this rare; kept defensive)."""
    if not text or not text.strip():
        raise ExtractionError("empty model response")
    cleaned = text.strip()
    if cleaned.startswith("```"):
        nl = cleaned.find("\n")
        if nl != -1:
            cleaned = cleaned[nl + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
    candidates = [cleaned]
    start = min((i for i in (cleaned.find("{"), cleaned.find("[")) if i != -1), default=-1)
    if start > 0:
        candidates.append(cleaned[start:])
    elif start == -1:
        raise ExtractionError("no JSON in model response")
    for cand in candidates:
        parsed = _try_parse(cand)
        if parsed is not None:
            return parsed
    raise ExtractionError("could not parse JSON from model response")


def _try_parse(text: str) -> list[dict] | None:
    if not text:
        return None
    opener = text[0]
    closer = "]" if opener == "[" else "}"
    for end in range(len(text), 0, -1):
        chunk = text[:end]
        if not chunk.endswith(closer):
            continue
        try:
            data = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            rows = data.get("rows", data.get("vehicles", []))
            if isinstance(rows, list):
                return [r for r in rows if isinstance(r, dict)]
        elif isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        return None
    return None


def _map_status(raw: str | None, has_exit: bool) -> str:
    text = (raw or "").lower()
    for keys, mapped in _STATUS_MAP:
        if any(k in text for k in keys):
            return mapped
    return "work_done" if has_exit else "in_progress"


def _clamp(x: object) -> float | None:
    try:
        v = float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, v))


def normalize_row(raw: dict, location_id: int | None) -> tuple[dict, dict]:
    entry_date = parse_date_loose(raw.get("entry_date"))
    out_date = parse_date_loose(raw.get("out_date"))
    in_time = parse_time_loose(raw.get("in_time"))
    out_time = parse_time_loose(raw.get("out_time"))
    has_exit = bool(out_date or out_time)
    status = _map_status(raw.get("status"), has_exit)
    payload = {
        "location_id": location_id,
        "sr_no": raw.get("sr_no") or None,
        "vrn": str(raw.get("vrn") or "").strip(),
        "model": (str(raw.get("model")).strip() or None) if raw.get("model") else None,
        "entry_date": fmt_date(entry_date),
        "in_time": fmt_time(in_time),
        "out_date": fmt_date(out_date),
        "out_time": fmt_time(out_time),
        "status": status,
        "remarks": (str(raw.get("remarks")).strip() or None) if raw.get("remarks") else None,
    }
    if payload["status"] == "work_done" and not payload["out_date"] and entry_date:
        payload["out_date"] = payload["entry_date"]

    model_conf = raw.get("confidence") if isinstance(raw.get("confidence"), dict) else {}
    confidence: dict[str, float] = {}
    for f in _FIELDS:
        given = _clamp(model_conf.get(f))
        confidence[f] = given if given is not None else _heuristic(f, raw, payload)
    return payload, confidence


def _heuristic(f: str, raw: dict, payload: dict) -> float:
    if f == "vrn":
        if is_valid_vrn(payload["vrn"]):
            return 0.85
        return 0.3 if payload["vrn"] else 0.1
    if f in ("entry_date", "in_time"):
        return 0.9 if payload[f] else 0.2
    if f in ("out_date", "out_time"):
        if payload[f]:
            return 0.9
        return 1.0 if payload["status"] == "in_progress" else 0.5
    if f == "model":
        return 0.7 if payload["model"] else 0.4
    if f == "status":
        return 0.9
    return 0.5


def boost_confidence_with_ocr(payload: dict, confidence: dict, ocr_text: str | None) -> dict:
    if not ocr_text:
        return confidence
    hay = ocr_text.upper().replace("-", "").replace(" ", "")
    vrn_norm = normalize_vrn(payload.get("vrn"))
    if vrn_norm and vrn_norm in hay:
        confidence["vrn"] = max(confidence.get("vrn", 0.0), 1.0)
    digits = "".join(c for c in (payload.get("vrn") or "") if c.isdigit())
    if digits and digits in hay.replace("-", ""):
        confidence["vrn"] = max(confidence.get("vrn", 0.0), 0.9)
    return confidence


async def extract_rows(
    spec: ProviderSpec, image_bytes: bytes, location_id: int | None = None
) -> ExtractionResult:
    processed, _meta = preprocess_image(image_bytes)
    ocr_text = ocr_service.run_ocr(processed)
    prompt = build_prompt(ocr_text)

    last_error: Exception | None = None
    raw = None
    for guided in (True, False):
        try:
            raw = await call_provider(spec, prompt, processed, guided=guided)
            rows_raw = parse_extraction_response(raw)
            break
        except ExtractionError as exc:
            last_error = exc
            rows_raw = None
    else:
        raise last_error or ExtractionError("extraction failed")

    result = ExtractionResult(
        provider=spec.kind,
        model=spec.model,
        ocr_available=ocr_service.ocr_available() and bool(ocr_text),
        raw_response=raw,
    )
    for raw_row in rows_raw:
        payload, confidence = normalize_row(raw_row, location_id)
        confidence = boost_confidence_with_ocr(payload, confidence, ocr_text)
        result.rows.append(payload)
        result.confidences.append(confidence)
    return result
