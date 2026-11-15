from datetime import date, datetime, time
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.models import ImportImage, ImportJob, ImportRow, LlmProvider, VehicleEntry
from app.services.dates import fmt_time, parse_date_loose, parse_time_loose
from app.services.vrn import is_valid_vrn

FieldErrors = dict[str, str]


# ---------------------------------------------------------------- auth/users

class LoginIn(BaseModel):
    username: str
    password: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: str
    location_id: int | None
    is_active: bool


class UserCreateIn(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    display_name: str = ""
    password: str = Field(min_length=8)
    role: Literal["admin", "operator", "viewer"] = "operator"
    location_id: int | None = None


class UserPatchIn(BaseModel):
    display_name: str | None = None
    role: Literal["admin", "operator", "viewer"] | None = None
    location_id: int | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8)


class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool


class LocationIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class LocationPatchIn(BaseModel):
    name: str | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------- entries

class EntryIn(BaseModel):
    location_id: int
    sr_no: int | None = None
    vrn: str = Field(min_length=1, max_length=32)
    model: str | None = None
    entry_date: date | None = None
    in_time: time | None = None
    out_date: date | None = None
    out_time: time | None = None
    status: Literal["work_done", "in_progress", "pending", "cancelled"] = "in_progress"
    remarks: str | None = None

    @field_validator("sr_no", mode="before")
    @classmethod
    def _sr_no(cls, v: Any) -> Any:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return int(v)

    @field_validator("entry_date", "out_date", mode="before")
    @classmethod
    def _date(cls, v: Any) -> Any:
        if isinstance(v, str):
            if not v.strip():
                return None
            parsed = parse_date_loose(v)
            if parsed is None:
                raise ValueError("invalid date")
            return parsed
        return v

    @field_validator("in_time", "out_time", mode="before")
    @classmethod
    def _time(cls, v: Any) -> Any:
        if isinstance(v, str):
            if not v.strip():
                return None
            parsed = parse_time_loose(v)
            if parsed is None:
                raise ValueError("invalid time")
            return parsed
        return v

    @field_validator("vrn")
    @classmethod
    def _vrn(cls, v: str) -> str:
        if not is_valid_vrn(v):
            raise ValueError("invalid VRN format (expected like AS-01-AB-1234)")
        return v.strip()

    @model_validator(mode="after")
    def _cross_field(self) -> "EntryIn":
        if self.out_date and not self.entry_date:
            raise ValueError("out_date requires entry_date")
        if self.out_date and self.entry_date and self.out_date < self.entry_date:
            raise ValueError("out_date before entry_date")
        if self.status == "work_done" and not self.out_date:
            raise ValueError("work_done requires out_date")
        if self.status == "in_progress" and self.out_date:
            raise ValueError("in_progress must not have out_date")
        return self


def validate_entry_payload(payload: dict) -> tuple[EntryIn | None, FieldErrors]:
    """Manual validation returning {field: message} instead of FastAPI's 422 shape."""
    try:
        return EntryIn.model_validate(payload), {}
    except Exception as exc:  # pydantic ValidationError
        errors: FieldErrors = {}
        for err in getattr(exc, "errors", lambda: [])():
            loc = ".".join(str(p) for p in err.get("loc", ()))
            msg = err.get("msg", "invalid")
            if not loc or loc == "__root__":
                # attribute root cross-field errors to the offending field
                lowered = msg.lower()
                if "vrn" in lowered:
                    loc = "vrn"
                elif "out_date" in lowered:
                    loc = "out_date"
                elif "entry_date" in lowered:
                    loc = "entry_date"
                else:
                    loc = "payload"
            errors.setdefault(loc, msg)
        return None, errors


class EntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    location_id: int
    sr_no: int | None
    vrn: str
    vrn_normalized: str
    model: str | None
    entry_date: date | None
    in_time: time | None
    out_date: date | None
    out_time: time | None
    status: str
    remarks: str | None
    source: str
    created_at: datetime
    updated_at: datetime
    location_name: str | None = None

    @field_serializer("in_time", "out_time")
    def _ser_time(self, v: time | None) -> str | None:
        return fmt_time(v)


def serialize_entry(entry: VehicleEntry, **extra: Any) -> dict:
    data = EntryOut.model_validate(entry).model_dump(mode="json")
    data["location_name"] = entry.location.name if entry.location else None
    data.update(extra)
    return data


class BulkEntryIn(BaseModel):
    items: list[dict] = Field(min_length=1, max_length=500)


# ---------------------------------------------------------------- vehicles

class VehicleSummaryOut(BaseModel):
    vrn_normalized: str
    display_vrn: str
    model_last: str | None
    visits: int
    first_seen: str | None
    last_seen: str | None
    open_entries: int


class TimelineEntryOut(BaseModel):
    entry: dict
    duration_hours: float | None
    flags: list[str] = []


class TimelineOut(BaseModel):
    vrn_normalized: str
    display_vrn: str
    entries: list[TimelineEntryOut]


# ---------------------------------------------------------------- dashboard

class LocationSummaryOut(BaseModel):
    location_id: int
    name: str
    entries_today: int
    open_wip: int


class OpenWipOut(BaseModel):
    entry: dict
    age_days: int


class WeekPointOut(BaseModel):
    date: str
    count: int


class DashboardOut(BaseModel):
    date: str
    per_location: list[LocationSummaryOut]
    open_wip: list[OpenWipOut]
    week_series: list[WeekPointOut]


# ---------------------------------------------------------------- providers

class ProviderCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    kind: Literal["openai", "gemini"] = "openai"
    base_url: str | None = None
    api_key: str | None = None
    default_model: str = ""


class ProviderPatchIn(BaseModel):
    name: str | None = None
    kind: Literal["openai", "gemini"] | None = None
    base_url: str | None = None
    api_key: str | None = None
    default_model: str | None = None
    enabled: bool | None = None
    supports_guided_json: bool | None = None
    disable_thinking: bool | None = None


class ProviderOut(BaseModel):
    id: int
    name: str
    kind: str
    base_url: str | None
    api_key_masked: str | None
    default_model: str
    is_default: bool
    enabled: bool
    supports_guided_json: bool
    disable_thinking: bool
    vision_status: str
    last_test: dict | None

    @classmethod
    def from_model(cls, p: LlmProvider, api_key_plain: str | None) -> "ProviderOut":
        from app.security import mask_secret

        return cls(
            id=p.id,
            name=p.name,
            kind=p.kind,
            base_url=p.base_url,
            api_key_masked=mask_secret(api_key_plain),
            default_model=p.default_model,
            is_default=p.is_default,
            enabled=p.enabled,
            supports_guided_json=p.supports_guided_json,
            disable_thinking=p.disable_thinking,
            vision_status=p.vision_status,
            last_test=p.last_test,
        )


# ---------------------------------------------------------------- settings

class SmtpIn(BaseModel):
    host: str | None = None
    port: int = 587
    username: str | None = None
    use_tls: bool = True
    from_address: str | None = None
    password: str | None = None  # None = keep stored


class EmailSettingsIn(BaseModel):
    enabled: bool = False
    recipients: list[str] = []
    schedule_time: str | None = None
    smtp: SmtpIn = SmtpIn()

    @field_validator("schedule_time")
    @classmethod
    def _sched(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        if parse_time_loose(v) is None:
            raise ValueError("schedule_time must be HH:MM")
        return fmt_time(parse_time_loose(v))


class EmailSettingsOut(BaseModel):
    enabled: bool
    recipients: list[str]
    schedule_time: str | None
    smtp: dict


class GeneralSettingsOut(BaseModel):
    display_date_format: str = "DD-MM-YYYY"
    rc_lookup_enabled: bool = False


class GeneralSettingsIn(BaseModel):
    display_date_format: str = "DD-MM-YYYY"
    rc_lookup_enabled: bool = False


# ---------------------------------------------------------------- imports

class ImportRowOut(BaseModel):
    id: int
    image_id: int
    payload: dict
    confidence: dict | None
    status: str
    edited_fields: list[str]
    committed_entry_id: int | None
    validation: dict

    @classmethod
    def from_model(cls, r: ImportRow) -> "ImportRowOut":
        _, errors = validate_entry_payload(r.payload or {})
        return cls(
            id=r.id,
            image_id=r.image_id,
            payload=r.payload or {},
            confidence=r.confidence,
            status=r.status,
            edited_fields=r.edited_fields or [],
            committed_entry_id=r.committed_entry_id,
            validation={"valid": not errors, "errors": errors},
        )


def row_validation(row: ImportRow) -> dict:
    _, errors = validate_entry_payload(row.payload or {})
    return {"valid": not errors, "errors": errors}


class ImportImageOut(BaseModel):
    id: int
    filename: str
    status: str
    error: str | None
    provider: str | None
    model: str | None
    ocr_available: bool
    rows: list[ImportRowOut]

    @classmethod
    def from_model(cls, img: ImportImage) -> "ImportImageOut":
        return cls(
            id=img.id,
            filename=img.filename,
            status=img.status,
            error=img.error,
            provider=img.provider,
            model=img.model,
            ocr_available=img.ocr_available,
            rows=[ImportRowOut.from_model(r) for r in img.rows],
        )


class ImportJobSummaryOut(BaseModel):
    id: int
    status: str
    created_at: str
    created_by_name: str
    provider_label: str | None
    error: str | None
    row_counts: dict[str, int]

    @classmethod
    def from_model(cls, job: ImportJob) -> "ImportJobSummaryOut":
        counts = {s: 0 for s in ("pending_review", "accepted", "rejected", "committed")}
        for img in job.images:
            for row in img.rows:
                if row.status in counts:
                    counts[row.status] += 1
        return cls(
            id=job.id,
            status=job.status,
            created_at=job.created_at.isoformat() if job.created_at else "",
            created_by_name=job.created_by_name,
            provider_label=job.provider_label,
            error=job.error,
            row_counts=counts,
        )


class ImportJobDetailOut(ImportJobSummaryOut):
    images: list[ImportImageOut]

    @classmethod
    def from_model(cls, job: ImportJob) -> "ImportJobDetailOut":
        base = ImportJobSummaryOut.from_model(job).model_dump()
        base["images"] = [ImportImageOut.from_model(i).model_dump() for i in job.images]
        return cls.model_validate(base)


class RowPatchIn(BaseModel):
    payload: dict | None = None
    status: Literal["accepted", "pending_review"] | None = None


class CommitIn(BaseModel):
    row_ids: list[int] | None = None


# ---------------------------------------------------------------- misc

def entry_search_matches(entry: VehicleEntry, q: str) -> bool:
    q = q.strip().upper()
    if not q:
        return True
    hay = " ".join(
        str(x or "") for x in (entry.vrn, entry.vrn_normalized, entry.model, entry.remarks)
    ).upper().replace("-", "").replace(" ", "")
    return q.replace("-", "").replace(" ", "") in hay
