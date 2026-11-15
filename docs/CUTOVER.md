# Cutover: v1 (app.py + vehicle_reports.db) → v2

Run v2 in parallel with v1 first; only switch users over after the import report is clean.

The v1 application and its database live in this repository's **`main` branch** history
(this branch contains only v2). Restore the v1 DB from there or from your local backup:

```bash
mkdir -p /tmp/v1 && git show main:vehicle_reports.db > /tmp/v1/vehicle_reports.db
# or: cp ~/backups/vehicle_report_v1_<date>/vehicle_reports.db /tmp/v1/
```

## 1. Backup

```bash
cp /tmp/v1/vehicle_reports.db /tmp/v1/vehicle_reports.backup-$(date +%F).db
```

## 2. Dry-run the migration (v1 DB is never written)

```bash
cd backend
uv run python scripts/migrate_v1.py \
  --old-db /tmp/v1/vehicle_reports.db \
  --new-db sqlite:///../data/app.db \
  --report /tmp/migration-exceptions.csv \
  --dry-run
```

Review the summary (2,944 rows, 6 locations) and the exception CSV (19 rows in the
current data: 18 with `out_date` before `entry_date` — likely year typos; 1 missing
entry date). Fix these in the v1 DB or accept them (they migrate flagged).

## 3. Real import

```bash
uv run python scripts/migrate_v1.py --old-db /tmp/v1/vehicle_reports.db --new-db sqlite:///../data/app.db
```

The script is **idempotent** (`legacy_id` unique) — safe to re-run.

For production (Postgres), point `--new-db` at the Postgres sync URL instead
(requires `uv pip install "psycopg[binary]"` in the backend env), or import into
the local sqlite first and `pg_dump`/`pg_restore`.

## 4. Verify in the UI

- Every depot appears under Locations with the right counts.
- Vehicles page: search a known VRN, history timeline spans v1 dates.
- Excel export of one day matches the v1 sheet you used to send.

## 5. LLM + email configuration

Settings → Providers: register the vision model (local vLLM/llama.cpp base_url or
Gemini key) and click **Test** (verifies models list + vision capability).
Settings → Email: SMTP + daily schedule replacing the Outlook COM hack.

## 6. Cut over users

- DNS/load-balancer → Caddy (deploy/docker-compose.yml) on the VPS.
- Keep v1 running read-only for one week (it has no editing requirement in practice);
  v1 is the fallback until users confirm v2 entries reconcile.
- After sign-off: archive the v1 repo directory, keep the v1 DB backup offline.

## Known data quirks carried over (visible to users)

- v1 `remarks` was the status source ("Work Done"/"Work In Progress") — mapped to
  `status`; unmapped values kept in remarks with `[migrated: status unmapped]`.
- ~130 dates were 2-digit years (interpreted as 20YY); 18 negative-duration rows are
  flagged `negative_duration` in the v2 timeline view.
