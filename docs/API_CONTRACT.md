# Vehicle Report v2 — API Contract (source of truth for backend & frontend)

Base URL: `/api`. All bodies JSON unless noted. Auth via HttpOnly cookie `vr_session`.
CSRF: non-safe methods (POST/PUT/PATCH/DELETE) must send header `X-CSRF-Token` matching cookie `vr_csrf` (obtained via `GET /api/auth/csrf`). Violation → 403 `{detail:"csrf_failed"}`.
Unauthenticated access to protected endpoints → 401. Wrong role → 403.

Enums:
- `Status = "work_done" | "in_progress" | "pending" | "cancelled"`
- `Source = "manual" | "ai_import"`
- `Role = "admin" | "operator" | "viewer"`
- `ProviderKind = "openai" | "gemini"`
- `VisionStatus = "unknown" | "supported" | "unsupported"`
- `ImportJobStatus = "queued" | "processing" | "done" | "partial" | "failed"`
- `ImportImageStatus = "queued" | "processing" | "extracted" | "failed"`
- `ImportRowStatus = "pending_review" | "accepted" | "rejected" | "committed"`

Roles per endpoint: `*` any authed user, `op` operator+admin, `adm` admin only.

## Shared object shapes

```ts
User = { id: number; username: string; display_name: string; role: Role; location_id: number|null; is_active: boolean }
Location = { id: number; name: string; is_active: boolean }
EntryCreate = {
  location_id: number; sr_no: number|null; vrn: string; model: string|null;
  entry_date: string|null /* YYYY-MM-DD */; in_time: string|null /* HH:MM */;
  out_date: string|null; out_time: string|null; status: Status; remarks: string|null
}
Entry = EntryCreate & {
  id: number; location_name: string; vrn_normalized: string /* AS01AB1234 */;
  source: Source; created_at: string; updated_at: string
}
Page<T> = { items: T[]; total: number; page: number; page_size: number }
EntryQuery = location_id?, status?, date_from? YYYY-MM-DD, date_to? YYYY-MM-DD, q? (matches vrn/model/remarks), page=1, page_size=25
```

## Auth
- `GET /api/auth/csrf` (public) → `{ csrf_token: string }` (also sets `vr_csrf` cookie)
- `POST /api/auth/login` (public) body `{username, password}` → `User`. Wrong creds → 401.
- `POST /api/auth/logout` * → `{ok:true}`
- `GET /api/auth/me` → `User` (401 if none)
- `POST /api/auth/change-password` body `{current_password, new_password}` → `{ok:true}` (400 if current wrong / too short)

## Users (adm)
- `GET /api/users` → `User[]`
- `POST /api/users` `{username, display_name, password, role, location_id?}` → `User`
- `PATCH /api/users/{id}` `{display_name?, role?, location_id?, is_active?, password?}` → `User`

## Locations
- `GET /api/locations` * → `Location[]`
- `POST /api/locations` (adm) `{name}` → `Location`
- `PATCH /api/locations/{id}` (adm) `{name?, is_active?}` → `Location`

## Entries
- `GET /api/entries?` + EntryQuery * → `Page<Entry>`
- `POST /api/entries` (op) EntryCreate → `Entry`
- `POST /api/entries/bulk` (op) `{items: EntryCreate[]}` → `{created: number[]}` (inserted ids)
- `PATCH /api/entries/{id}` (op) partial EntryCreate → `Entry`
- `DELETE /api/entries/{id}` (adm) → `{ok:true}`

## Vehicles
- `GET /api/vehicles?q=<vrn-prefix-or-substring>&limit=20` * → `{items: VehicleSummary[]}`
  `VehicleSummary = { vrn_normalized: string; display_vrn: string /* AS-01-AB-1234 */; model_last: string|null; visits: number; first_seen: string|null /* date */; last_seen: string|null; open_entries: number }`
- `GET /api/vehicles/{vrn_normalized}/timeline` * → `{ vrn_normalized, display_vrn, entries: (Entry & { duration_hours: number|null })[] }` (desc by entry_date)
  anomalies: client-side derive is fine (duration<0, same vrn open at 2 locations same day) — backend also returns `flags: string[]` per entry (`open_record`, `negative_duration`).

## Dashboard
- `GET /api/dashboard/summary` * →
```ts
{ date: string /* today ISO */;
  per_location: { location_id: number; name: string; entries_today: number; open_wip: number }[];
  open_wip: (Entry & { age_days: number })[];           // in_progress, oldest first, max 50
  week_series: { date: string; count: number }[] }      // last 7 days totals
```

## Imports (AI image → review → commit)
- `POST /api/imports` (op) multipart/form-data: `files` (1..20 images), optional `provider_id`, `location_id` → `{job_id}`
- `GET /api/imports?page&page_size` * → `Page<ImportJobSummary>`
- `GET /api/imports/{id}` * → `ImportJobDetail`
- `GET /api/imports/{id}/images/{image_id}/file` * → image bytes
- `PATCH /api/imports/rows/{row_id}` (op) `{payload?: EntryCreate, status?: "accepted"|"pending_review"}` → `ImportRow` (payload re-validated server-side; invalid → 422 `{detail:{errors: Record<field,string>}}`)
- `POST /api/imports/rows/{row_id}/reject` (op) → `ImportRow`
- `POST /api/imports/{id}/commit` (op) `{row_ids?: number[]}` (omit = all `accepted` rows) → `{committed: number, entry_ids: number[]}`; rows→`committed`, entries created `source:"ai_import"`. 400 if any requested row not `accepted`.
- `POST /api/imports/{id}/images/{image_id}/retry` (op) → `{job_id}` (re-extracts just that image)

```ts
ImportJobSummary = { id: number; status: ImportJobStatus; created_at: string; created_by_name: string;
  provider_label: string|null; error: string|null;
  row_counts: { pending_review: number; accepted: number; rejected: number; committed: number } }
ImportJobDetail = ImportJobSummary & { images: ImportImage[] }
ImportImage = { id: number; filename: string; status: ImportImageStatus; error: string|null;
  provider: string|null; model: string|null; ocr_available: boolean; rows: ImportRow[] }
ImportRow = { id: number; image_id: number; payload: EntryCreate;
  confidence: Record<string, number>|null; // 0..1 per field
  status: ImportRowStatus;
  validation: { valid: boolean; errors: Record<string,string> };
  edited_fields: string[]; committed_entry_id: number|null }
```

## Settings — LLM providers (adm)
- `GET /api/settings/providers` → `Provider[]`
- `POST /api/settings/providers` `{name, kind, base_url?, api_key?, default_model}` → `Provider`
- `PATCH /api/settings/providers/{id}` `{name?, kind?, base_url?, api_key?, default_model?, enabled?, supports_guided_json?, disable_thinking?}` → `Provider` (api_key omitted = keep)
- `DELETE /api/settings/providers/{id}` → `{ok:true}`
- `POST /api/settings/providers/{id}/test` → `{ok: boolean; message: string; models: string[]; vision: VisionStatus}` (also persists last_test/vision_status)
- `POST /api/settings/providers/{id}/default` → `{ok:true}`
```ts
Provider = { id: number; name: string; kind: ProviderKind; base_url: string|null;
  api_key_masked: string|null; default_model: string; is_default: boolean; enabled: boolean;
  supports_guided_json: boolean; disable_thinking: boolean; vision_status: VisionStatus;
  last_test: {ok:boolean; message:string; at:string}|null }
```

## Settings — email & general
- `GET /api/settings/email` (adm) → `EmailSettings` ; `PUT /api/settings/email` (adm) `EmailSettings` (omit smtp.password = keep) → `EmailSettings`
- `POST /api/settings/email/test` (adm) → `{ok, message}`
```ts
EmailSettings = { enabled: boolean; recipients: string[]; schedule_time: string|null /* "HH:MM" daily, server TZ */;
  smtp: { host: string|null; port: number; username: string|null; use_tls: boolean; from_address: string|null; password_set: boolean } }
```
- `GET /api/settings/general` * → `GeneralSettings` ; `PUT /api/settings/general` (adm) → `GeneralSettings`
```ts
GeneralSettings = { display_date_format: string /* default "DD-MM-YYYY" */; rc_lookup_enabled: boolean }
```

## RC lookup (optional feature)
- `GET /api/rc/{raw_vrn}` * → `{status:"ok", source:string, cached:boolean, payload: Record<string,string>} | {status:"disabled"|"unavailable"|"not_found", message?:string}`

## Exports
- `GET /api/exports/entries.xlsx?<EntryQuery>` * → xlsx file download (Content-Disposition attachment)
- `POST /api/exports/email-report` (adm) body `{date?}` (default today) → `{ok, message}`

## Misc
- `GET /api/health` (public) → `{status:"ok", version:string}`

Display notes for frontend: dates render `DD-MM-YYYY`, times 24h `HH:MM`; VRN inputs auto-format `AS-01-AB-1234` on blur.
