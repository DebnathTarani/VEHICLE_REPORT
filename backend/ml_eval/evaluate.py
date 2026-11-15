"""CLI harness: run app.services.extraction.extract_rows over golden cases and score.

    uv run python -m ml_eval.evaluate --openai-base http://localhost:8000 --model NAME
    uv run python -m ml_eval.evaluate --provider-id 1 [--golden-dir ../ml/golden] \
        [--out ml_eval/report.json] [--limit N]

Exit codes: 0 = completed, 1 = some case failed to extract, 2 = bad args / provider
unreachable (connect errors are caught; the run aborts fast instead of hanging).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from app.services.extraction import extract_rows, provider_spec  # noqa: E402
from app.services.providers.base import ExtractionError, ProviderSpec  # noqa: E402
from ml_eval import scoring  # noqa: E402

_DEFAULT_GOLDEN = Path(__file__).resolve().parents[2] / "ml" / "golden"


class HarnessError(Exception):
    """Bad arguments / unusable provider — exit code 2."""


def load_spec_from_db(provider_id: int) -> ProviderSpec:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.config import get_settings
    from app.models import LlmProvider

    url = get_settings().database_url
    for suffix in ("+aiosqlite", "+asyncpg"):
        url = url.replace(suffix, "")
    engine = create_engine(url)
    try:
        with Session(engine) as session:
            provider = session.get(LlmProvider, provider_id)
            if provider is None:
                raise HarnessError(f"no LlmProvider with id {provider_id} in app db")
            return provider_spec(provider)
    finally:
        engine.dispose()


def build_spec(args: argparse.Namespace) -> ProviderSpec:
    if args.provider_id is not None:
        return load_spec_from_db(args.provider_id)
    if args.openai_base and args.model:
        return ProviderSpec(
            kind="openai",
            base_url=args.openai_base,
            api_key=os.environ.get("OPENAI_API_KEY"),
            model=args.model,
            timeout=args.timeout,
        )
    raise HarnessError(
        "provide either --openai-base URL together with --model NAME, or --provider-id N"
    )


def load_cases(golden_dir: Path, limit: int | None) -> list[dict]:
    manifest = golden_dir / "cases.json"
    if not manifest.exists():
        raise HarnessError(
            f"manifest not found: {manifest} "
            "(generate it with: uv run python ml_eval/make_synthetic_cases.py)"
        )
    cases = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise HarnessError(f"empty or invalid manifest: {manifest}")
    return cases[:limit] if limit else cases


def run_case(spec: ProviderSpec, case: dict, golden_dir: Path) -> dict:
    image_path = golden_dir / case["image"]
    if not image_path.exists():
        raise FileNotFoundError(f"image not found: {image_path}")
    image_bytes = image_path.read_bytes()
    result = asyncio.run(extract_rows(spec, image_bytes, location_id=case.get("location_id")))
    return {
        "case": case["case"],
        "image": case["image"],
        "expected_rows": len(case.get("expected_rows", [])),
        "actual_rows": len(result.rows),
        "provider": result.provider,
        "model": result.model,
        "ocr_available": result.ocr_available,
        "error": None,
        **scoring.score_case(case.get("expected_rows", []), result.rows),
    }


def print_report(agg: dict, per_case: list[dict], spec: ProviderSpec) -> None:
    width = 52
    print("=" * width)
    print(f"ML extraction eval  provider={spec.kind} model={spec.model} base={spec.base_url}")
    print("=" * width)
    print(f"{'field':<14}{'accuracy':>10}  correct/total")
    for field, acc in agg["per_field_accuracy"].items():
        if acc is None:
            print(f"{field:<14}{'n/a':>10}  0/0")
        else:
            print(
                f"{field:<14}{acc:>10.3f}  "
                f"{agg['per_field_correct'][field]}/{agg['per_field_total'][field]}"
            )
    print("-" * width)
    for case in per_case:
        status = "ERROR" if case["error"] else (
            "PASS"
            if case["missing"] == 0
            and case["extra"] == 0
            and all(all(r.values()) for r in case["rows"])
            else "FAIL"
        )
        detail = (
            f"expected={case['expected_rows']} actual={case['actual_rows']} "
            f"missing={case['missing']} extra={case['extra']}"
        )
        if case["error"]:
            detail = case["error"]
        print(f"{status:<6} {case['case']:<12} {detail}")
    print("-" * width)
    print(
        f"cases: {agg['cases_total']} (fully correct {agg['cases_fully_correct']})   "
        f"rows: {agg['rows_total']} (fully correct {agg['rows_fully_correct']})   "
        f"missing {agg['missing_rows']} / extra {agg['extra_rows']}"
    )
    print("=" * width)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate ML extraction against golden cases")
    parser.add_argument("--openai-base", default=None, help="OpenAI-compatible base URL")
    parser.add_argument("--model", default=None, help="model name for --openai-base")
    parser.add_argument(
        "--provider-id", type=int, default=None, help="load LlmProvider by id from the app db"
    )
    parser.add_argument("--golden-dir", default=str(_DEFAULT_GOLDEN), help="golden set directory")
    parser.add_argument("--out", default="ml_eval/report.json", help="JSON report path")
    parser.add_argument("--limit", type=int, default=None, help="evaluate only first N cases")
    parser.add_argument("--timeout", type=float, default=60.0, help="per-request timeout (s)")
    args = parser.parse_args(argv)

    golden_dir = Path(args.golden_dir)
    try:
        cases = load_cases(golden_dir, args.limit)
        spec = build_spec(args)
    except HarnessError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    per_case: list[dict] = []
    errored = 0
    for case in cases:
        try:
            per_case.append(run_case(spec, case, golden_dir))
        except (httpx.TransportError, ConnectionError, OSError) as exc:
            print(
                f"error: provider unreachable at {spec.openai_base()} ({type(exc).__name__}: {exc})\n"
                "check the base URL / that the server is running; aborting.",
                file=sys.stderr,
            )
            return 2
        except (ExtractionError, FileNotFoundError, ValueError) as exc:
            errored += 1
            per_case.append(
                {
                    "case": case["case"],
                    "image": case["image"],
                    "expected_rows": len(case.get("expected_rows", [])),
                    "actual_rows": 0,
                    "provider": spec.kind,
                    "model": spec.model,
                    "ocr_available": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "rows": [],
                    "missing": len(case.get("expected_rows", [])),
                    "extra": 0,
                }
            )

    agg = scoring.aggregate(per_case)
    print_report(agg, per_case, spec)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "provider": spec.kind,
                "base_url": spec.base_url,
                "model": spec.model,
                "golden_dir": str(golden_dir),
                "aggregate": agg,
                "cases": per_case,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"report written: {out_path}")
    return 1 if errored else 0


if __name__ == "__main__":
    sys.exit(main())
