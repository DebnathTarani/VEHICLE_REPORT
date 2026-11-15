"""Generate the synthetic golden set: register-page PNGs + cases.json manifest.

    uv run python ml_eval/make_synthetic_cases.py [--out-dir ../ml/golden]

Each case is <out-dir>/case_NNN/image.png (a drawn service-register table with
header + 3 vehicle rows) plus a matching expected_rows entry in cases.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

COLUMNS = [
    ("sr", "SR", 50),
    ("vrn", "VRN", 210),
    ("model", "MODEL", 240),
    ("entry_date", "ENTRY DATE", 150),
    ("in_time", "IN TIME", 110),
    ("out_date", "OUT DATE", 150),
    ("out_time", "OUT TIME", 120),
    ("remarks", "REMARKS", 260),
]

CASES = [
    {
        "case": "case_001",
        "title": "VEHICLE SERVICE REGISTER - JHAPIRBOND",
        "date_label": "DATE: 07-02-2026",
        "location_id": 1,
        "rows": [
            {
                "sr": "1",
                "vrn": "AS-01-AB-1234",
                "model": "MARUTI BOLERO",
                "entry_date": "07-02-2026",
                "in_time": "10:30",
                "out_date": "",
                "out_time": "",
                "status": "in_progress",
                "remarks": "general servicing",
            },
            {
                "sr": "2",
                "vrn": "NL05C 4521",
                "model": "TATA ACE",
                "entry_date": "07-02-2026",
                "in_time": "11:15",
                "out_date": "07-02-2026",
                "out_time": "14:45",
                "status": "work_done",
                "remarks": "brake job done",
            },
            {
                "sr": "3",
                "vrn": "AS-02-C-9911",
                "model": "MAHINDRA SCORPIO",
                "entry_date": "07-02-2026",
                "in_time": "12:05",
                "out_date": "",
                "out_time": "",
                "status": "in_progress",
                "remarks": "waiting for parts",
            },
        ],
    },
    {
        "case": "case_002",
        "title": "VEHICLE SERVICE REGISTER - KARIMGANJ",
        "date_label": "DATE: 08-02-2026",
        "location_id": 2,
        "rows": [
            {
                "sr": "1",
                "vrn": "ML04 EF 5678",
                "model": "TATA SUMO",
                "entry_date": "08-02-2026",
                "in_time": "09:40",
                "out_date": "08-02-2026",
                "out_time": "12:10",
                "status": "work_done",
                "remarks": "oil change complete",
            },
            {
                "sr": "2",
                "vrn": "TR01J 0012",
                "model": "FORCE TEMPO",
                "entry_date": "08-02-2026",
                "in_time": "10:05",
                "out_date": "",
                "out_time": "",
                "status": "in_progress",
                "remarks": "clutch work",
            },
            {
                "sr": "3",
                "vrn": "AS-01-B-0455",
                "model": "TATA ACE GOLD",
                "entry_date": "08-02-2026",
                "in_time": "11:20",
                "out_date": "08-02-2026",
                "out_time": "13:55",
                "status": "work_done",
                "remarks": "tyre replacement done",
            },
        ],
    },
]

_EXPECTED_FIELDS = (
    "vrn",
    "model",
    "entry_date",
    "in_time",
    "out_date",
    "out_time",
    "status",
)


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # pragma: no cover - old Pillow
        return ImageFont.load_default()


def render_case(case: dict) -> Image.Image:
    row_h, head_h, pad = 46, 52, 14
    width = sum(c[2] for c in COLUMNS) + 2 * pad
    height = 2 * head_h + (len(case["rows"]) + 1) * row_h + 2 * pad + 40
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    f_title = _font(30)
    f_head = _font(22)
    f_cell = _font(22)

    draw.text((pad, pad), case["title"], fill="black", font=f_title)
    draw.text((width - pad - 300, pad + 6), case["date_label"], fill="black", font=_font(20))

    top = pad + 44
    x0, x1 = pad, width - pad
    draw.rectangle([x0, top, x1, top + head_h], outline="black", width=2)
    x = x0
    for _key, label, col_w in COLUMNS:
        draw.text((x + 8, top + head_h // 2 - 12), label, fill="black", font=f_head)
        x += col_w
        if x < x1:
            draw.line([x, top, x, top + head_h], fill="black", width=1)

    body_top = top + head_h
    n_rows = len(case["rows"]) + 1
    draw.rectangle([x0, body_top, x1, body_top + n_rows * row_h], outline="black", width=2)
    x = x0
    for _key, _label, col_w in COLUMNS:
        x += col_w
        if x < x1:
            draw.line([x, body_top, x, body_top + n_rows * row_h], fill="black", width=1)
    for r in range(1, n_rows):
        y = body_top + r * row_h
        draw.line([x0, y, x1, y], fill="black", width=1)

    for i, row in enumerate(case["rows"]):
        y = body_top + i * row_h + row_h // 2 - 12
        x = x0
        for key, _label, col_w in COLUMNS:
            draw.text((x + 8, y), str(row.get(key, "")), fill="black", font=f_cell)
            x += col_w
    return img


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out-dir",
        default=str(Path(__file__).resolve().parents[2] / "ml" / "golden"),
        help="golden set directory (default: <repo>/ml/golden)",
    )
    args = parser.parse_args(argv)
    out_dir = Path(args.out_dir)

    manifest = []
    for case in CASES:
        case_dir = out_dir / case["case"]
        case_dir.mkdir(parents=True, exist_ok=True)
        image_path = case_dir / "image.png"
        render_case(case).save(image_path, format="PNG")
        manifest.append(
            {
                "case": case["case"],
                "image": f"{case['case']}/image.png",
                "location_id": case["location_id"],
                "expected_rows": [
                    {f: row[f] for f in _EXPECTED_FIELDS} for row in case["rows"]
                ],
            }
        )
        print(f"wrote {image_path}")

    (out_dir / "cases.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {out_dir / 'cases.json'} ({len(manifest)} cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
