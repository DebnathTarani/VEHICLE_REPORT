export type Status = "work_done" | "in_progress" | "pending" | "cancelled";
export type Source = "manual" | "ai_import";
export type Role = "admin" | "operator" | "viewer";
export type ProviderKind = "openai" | "gemini";
export type VisionStatus = "unknown" | "supported" | "unsupported";
export type ImportJobStatus = "queued" | "processing" | "done" | "partial" | "failed";
export type ImportImageStatus = "queued" | "processing" | "extracted" | "failed";
export type ImportRowStatus = "pending_review" | "accepted" | "rejected" | "committed";

export interface User {
  id: number;
  username: string;
  display_name: string;
  role: Role;
  location_id: number | null;
  is_active: boolean;
}

export interface Location {
  id: number;
  name: string;
  is_active: boolean;
}

export interface EntryCreate {
  location_id: number;
  sr_no: number | null;
  vrn: string;
  model: string | null;
  entry_date: string | null; // YYYY-MM-DD
  in_time: string | null; // HH:MM
  out_date: string | null;
  out_time: string | null;
  status: Status;
  remarks: string | null;
}

export interface Entry extends EntryCreate {
  id: number;
  location_name: string;
  vrn_normalized: string; // AS01AB1234
  source: Source;
  created_at: string;
  updated_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface EntryQuery {
  location_id?: number;
  status?: Status;
  date_from?: string; // YYYY-MM-DD
  date_to?: string; // YYYY-MM-DD
  q?: string;
  page?: number;
  page_size?: number;
}

export interface VehicleSummary {
  vrn_normalized: string;
  display_vrn: string; // AS-01-AB-1234
  model_last: string | null;
  visits: number;
  first_seen: string | null; // date
  last_seen: string | null;
  open_entries: number;
}

export interface VehicleSearchResult {
  items: VehicleSummary[];
}

export interface TimelineEntry extends Entry {
  duration_hours: number | null;
  flags?: string[];
}

export interface VehicleTimeline {
  vrn_normalized: string;
  display_vrn: string;
  entries: TimelineEntry[];
}

export interface DashboardLocation {
  location_id: number;
  name: string;
  entries_today: number;
  open_wip: number;
}

export interface DashboardWipEntry extends Entry {
  age_days: number;
}

export interface DashboardWeekPoint {
  date: string;
  count: number;
}

export interface DashboardSummary {
  date: string; // today ISO
  per_location: DashboardLocation[];
  open_wip: DashboardWipEntry[]; // in_progress, oldest first, max 50
  week_series: DashboardWeekPoint[]; // last 7 days totals
}

export interface ImportRowCounts {
  pending_review: number;
  accepted: number;
  rejected: number;
  committed: number;
}

export interface ImportJobSummary {
  id: number;
  status: ImportJobStatus;
  created_at: string;
  created_by_name: string;
  provider_label: string | null;
  error: string | null;
  row_counts: ImportRowCounts;
}

export interface ImportRowValidation {
  valid: boolean;
  errors: Record<string, string>;
}

export interface ImportRow {
  id: number;
  image_id: number;
  payload: EntryCreate;
  confidence: Record<string, number> | null; // 0..1 per field
  status: ImportRowStatus;
  validation: ImportRowValidation;
  edited_fields: string[];
  committed_entry_id: number | null;
}

export interface ImportImage {
  id: number;
  filename: string;
  status: ImportImageStatus;
  error: string | null;
  provider: string | null;
  model: string | null;
  ocr_available: boolean;
  rows: ImportRow[];
}

export interface ImportJobDetail extends ImportJobSummary {
  images: ImportImage[];
}

export interface ImportJobCreateResult {
  job_id: number;
}

export interface ImportCommitResult {
  committed: number;
  entry_ids: number[];
}

export interface CsrfResponse {
  csrf_token: string;
}

export interface OkResponse {
  ok: boolean;
}

export interface MessageResponse {
  ok: boolean;
  message: string;
}

export interface ProviderTestResult {
  ok: boolean;
  message: string;
  models: string[];
  vision: VisionStatus;
}

export interface ProviderLastTest {
  ok: boolean;
  message: string;
  at: string;
}

export interface Provider {
  id: number;
  name: string;
  kind: ProviderKind;
  base_url: string | null;
  api_key_masked: string | null;
  default_model: string;
  is_default: boolean;
  enabled: boolean;
  supports_guided_json: boolean;
  disable_thinking: boolean;
  vision_status: VisionStatus;
  last_test: ProviderLastTest | null;
}

export interface ProviderCreate {
  name: string;
  kind: ProviderKind;
  base_url?: string | null;
  api_key?: string | null;
  default_model: string;
}

export interface ProviderUpdate {
  name?: string;
  kind?: ProviderKind;
  base_url?: string | null;
  api_key?: string | null;
  default_model?: string;
  enabled?: boolean;
  supports_guided_json?: boolean;
  disable_thinking?: boolean;
}

export interface SmtpSettings {
  host: string | null;
  port: number;
  username: string | null;
  use_tls: boolean;
  from_address: string | null;
  password_set: boolean;
}

export interface EmailSettings {
  enabled: boolean;
  recipients: string[];
  schedule_time: string | null; // "HH:MM" daily, server TZ
  smtp: SmtpSettings;
}

export interface GeneralSettings {
  display_date_format: string; // default "DD-MM-YYYY"
  rc_lookup_enabled: boolean;
}

export interface UserCreate {
  username: string;
  display_name: string;
  password: string;
  role: Role;
  location_id?: number | null;
}

export interface UserUpdate {
  display_name?: string;
  role?: Role;
  location_id?: number | null;
  is_active?: boolean;
  password?: string;
}

export type RcLookupResult =
  | { status: "ok"; source: string; cached: boolean; payload: Record<string, string> }
  | { status: "disabled" | "unavailable" | "not_found"; message?: string };
