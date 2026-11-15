# AI Extraction Quality Harness

The v1 app auto-inserted model output. v2 makes extraction measurable and reviewable:
every import lands in a **review queue** and a human commits rows. This harness measures
how good the model is so you can compare providers/models before switching defaults.

## Pipeline (backend/app/services/extraction.py)

1. Image preprocessing (EXIF fix, resize, OpenCV deskew + CLAHE contrast + unsharp;
   skipped gracefully when the `ml` extra is not installed).
2. Optional OCR grounding text (RapidOCR) injected into the prompt — never trusted as
   truth, used to verify character-level readings of VRNs/times.
3. Single JSON-schema-guided call (`guided_json` on vLLM, `responseSchema` on Gemini)
   so the model cannot return malformed JSON.
4. Deterministic decoding (temperature 0) and a versioned prompt
   (`app/ml_assets/prompt_v1.md` — bump the file, keep old ones for comparison).
5. Pydantic validation per row → invalid rows show field-level errors in the review UI
   and cannot be accepted until edited.

## Golden set

`ml/golden/` contains `cases.json` + page images with known expected rows.
Synthetic seed cases can be regenerated with:

```bash
cd backend
uv run python -m ml_eval.make_synthetic_cases
```

Add real register photos (redact/blur owner names if needed) as new `case_NNN/image.png`
entries in `cases.json` — this is the regression set for prompt/model changes.

## Scoring

```bash
cd backend

# against a local OpenAI-compatible vision server
uv run python -m ml_eval.evaluate --openai-base http://localhost:8000 --model Qwen2.5-VL-7B

# or against a provider saved in the app DB (Settings → Providers)
uv run python -m ml_eval.evaluate --provider-id 1 --out ml_eval/report.json
```

Reports per-field accuracy (VRN exact-match after normalization, date, times, status),
rows fully correct, and writes JSON for trend tracking. Suggested gates before making a
model the default: **VRN ≥ 0.97, entry_date ≥ 0.95, row-perfect ≥ 0.90**.

## Operational review rules (enforced by the backend)

- `POST /api/imports` → rows are `pending_review`; there is **no code path** that
  inserts AI rows into `vehicle_entries` without `status=accepted` + a commit call.
- `PATCH /api/imports/rows/{id}` re-validates server-side (422 with field errors keeps
  Accept blocked); `edited_fields` and model confidences are kept for auditability.
- Committed rows link `committed_entry_id`; jobs store the provider/model used and the
  original image, so any decision can be re-audited or re-extracted.
