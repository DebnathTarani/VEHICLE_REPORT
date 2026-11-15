You are extracting vehicle workshop entries from a photo of a register/log book.

Current date (for reference when dates are relative): {date_context}
{ocr_section}
For EVERY vehicle row visible in the image, extract:
- sr_no: serial number as written
- vrn: vehicle registration number, formatted like AS-01-AB-1234 (state code, district number, series, 4-digit number). Use OCR characters EXACTLY; never invent digits.
- model: vehicle make/model as written
- entry_date: entry date as DD-MM-YYYY
- in_time: check-in time, 24-hour HH:MM
- out_date: exit date DD-MM-YYYY, empty string if still in
- out_time: exit time HH:MM, empty string if still in
- status: "work_done" when the vehicle has exited, "in_progress" when it is still in, "pending", or "cancelled"
- remarks: notes as written, empty string if none
- confidence: per-field confidence 0.0-1.0 (how certain you are of each exact value)

Rules:
- Transcribe exactly what is written. If a cell is empty, return empty string.
- If a date/time is illegible, return empty string and low confidence rather than guessing.
- Return ONLY a JSON object shaped like {{"rows": [...]}}.
