import io

from openpyxl import Workbook
from openpyxl.styles import Font

from app.models import VehicleEntry
from app.services.dates import fmt_date, fmt_time

HEADERS = [
    "Location",
    "Sr No",
    "VRN",
    "Model",
    "Entry Date",
    "In Time",
    "Out Date",
    "Out Time",
    "Status",
    "Remarks",
]


def _display_date(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        y, m, d = iso.split("-")
        return f"{d}-{m}-{y}"
    except ValueError:
        return iso


def entry_row(entry: VehicleEntry) -> list:
    location = entry.location.name if entry.location else ""
    entry_date = fmt_date(entry.entry_date)
    out_date = fmt_date(entry.out_date)
    return [
        location,
        entry.sr_no if entry.sr_no is not None else "",
        entry.vrn,
        entry.model or "",
        _display_date(entry_date),
        fmt_time(entry.in_time) or "",
        _display_date(out_date),
        fmt_time(entry.out_time) or "",
        entry.status,
        entry.remarks or "",
    ]


def build_workbook(entries: list[VehicleEntry], title: str = "Vehicle Report") -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]
    ws.append(HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for e in entries:
        ws.append(entry_row(e))
    widths = [16, 8, 16, 20, 12, 10, 12, 10, 14, 30]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[chr(64 + i)].width = w
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
