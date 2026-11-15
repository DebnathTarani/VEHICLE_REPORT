import enum


class Role(str, enum.Enum):
    admin = "admin"
    operator = "operator"
    viewer = "viewer"


class EntryStatus(str, enum.Enum):
    work_done = "work_done"
    in_progress = "in_progress"
    pending = "pending"
    cancelled = "cancelled"


class EntrySource(str, enum.Enum):
    manual = "manual"
    ai_import = "ai_import"


class ProviderKind(str, enum.Enum):
    openai = "openai"
    gemini = "gemini"


class VisionStatus(str, enum.Enum):
    unknown = "unknown"
    supported = "supported"
    unsupported = "unsupported"


class ImportJobStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    done = "done"
    partial = "partial"
    failed = "failed"


class ImportImageStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    extracted = "extracted"
    failed = "failed"


class ImportRowStatus(str, enum.Enum):
    pending_review = "pending_review"
    accepted = "accepted"
    rejected = "rejected"
    committed = "committed"
