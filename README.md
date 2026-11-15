# Vehicle Report v2

Production-grade rebuild of the depot vehicle workshop register: multi-location entry,
AI photo import with mandatory human review, vehicle history, Excel/SMTP reporting,
dynamic LLM provider configuration, and a modern light React UI.

Built to replace the v1 prototype (Flask `app.py` + `vehicle_reports.db`), preserved in this
repository's `main` branch. See `docs/CUTOVER.md` to migrate the
existing `vehicle_reports.db`, and `docs/AI_EVAL.md` for the extraction quality harness.

## Stack

| Layer     | Choice |
|-----------|--------|
| API       | FastAPI + Pydantic v2 (typed, server-side validation on every write) |
| DB        | SQLAlchemy 2 (async) + Alembic — SQLite (dev) / Postgres (prod) |
| Auth      | Session cookie + CSRF double-submit; roles: admin / operator / viewer; audit log |
| AI        | Any OpenAI-compatible endpoint (vLLM, llama.cpp, …) or Gemini, with guided-JSON extraction, image preprocessing and optional OCR grounding (RapidOCR) |
| Frontend  | React 18 + Vite + TS + Tailwind (light theme default, dark mode), TanStack Query/Table |
| Deploy    | Multi-stage Dockerfile → app image; `docker compose` = Postgres + app + Caddy (TLS) |

## Layout

```
backend/            FastAPI app
  app/api/          routers (auth, entries, imports, providers, exports, …)
  app/services/     extraction pipeline, providers, OCR, image prep, email, jobs
  app/ml_assets/    versioned extraction prompt (prompt_v1.md)
  scripts/migrate_v1.py   v1 DB importer (idempotent, exception report)
  ml_eval/          per-field accuracy harness + golden-set generator
  tests/            53 pytest tests (API, RBAC, review-queue flow, parsing, eval)
frontend/           React app (npm)
deploy/             Dockerfile, docker-compose.yml, Caddyfile
docs/               API_CONTRACT.md (binding), CUTOVER.md, AI_EVAL.md
ml/golden/          synthetic golden images + cases.json
```

## Quickstart (development)

```bash
# backend
cd backend
uv sync --extra dev --extra ml          # ml extra = OpenCV prep + RapidOCR (optional but recommended)
uv run uvicorn app.main:app --reload --port 8000
# first start prints a one-time admin password (or set BOOTSTRAP_ADMIN_PASSWORD)

# frontend (separate shell)
cd frontend
npm install && npm run dev              # http://localhost:5173, proxies API to :8000
```

Open http://localhost:5173 → log in → **Settings → Providers** → add your vision LLM
(e.g. `kind=openai`, `base_url=http://localhost:8000`, model `Qwen2.5-VL`, click **Test**),
then **Locations** → add depots. Import register photos from **Imports**; nothing is
written to the database until rows are **accepted and committed**.

## Tests / quality gates

```bash
cd backend  && uv run ruff check app tests scripts ml_eval && uv run pytest -q
cd frontend && npm run test && npm run build
```

## Production deploy (VPS)

```bash
cd deploy
cat > .env <<EOF
POSTGRES_PASSWORD=<strong-random>
SECRET_KEY=$(python -c "import secrets;print(secrets.token_urlsafe(48))")
BOOTSTRAP_ADMIN_USERNAME=admin
BOOTSTRAP_ADMIN_PASSWORD=<initial-admin-password>
CADDY_SITE_ADDRESS=reports.your-domain.com
EOF
docker compose up -d --build
```

Schema is migrated by Alembic on container start (`alembic upgrade head`).
Images uploaded for import are stored in the `appdata` volume.

## Security posture

- `debug=False` always; no `/debug_db`-style endpoints.
- All mutating endpoints require auth + CSRF token; RBAC enforced server-side.
- LLM provider API keys and SMTP passwords encrypted at rest (Fernet/`SECRET_KEY`).
- Uploads validated by magic bytes (PIL verify), size and count capped.
- AI rows are never auto-inserted — human review + audit trail before commit.
