import { describe, expect, it } from "vitest";
import { validateEntryRow, rowToEntryCreate } from "./validation";

const validRow = {
  location_id: 1,
  vrn: "AS-01-AB-1234",
  model: "Swift",
  entry_date: "2026-11-15",
  in_time: "09:30",
  out_date: "2026-11-15",
  out_time: "17:45",
  status: "work_done" as const,
  remarks: null,
};

describe("validateEntryRow", () => {
  it("accepts a fully valid row", () => {
    expect(validateEntryRow(validRow)).toEqual({});
  });

  it("requires a VRN", () => {
    const errors = validateEntryRow({ ...validRow, vrn: "" });
    expect(errors.vrn).toBeTruthy();
  });

  it("rejects a malformed VRN", () => {
    const errors = validateEntryRow({ ...validRow, vrn: "1234-AB" });
    expect(errors.vrn).toBeTruthy();
  });

  it("rejects an invalid entry_date", () => {
    const errors = validateEntryRow({ ...validRow, entry_date: "15-11-2026" });
    expect(errors.entry_date).toBeTruthy();
  });

  it("rejects an invalid time", () => {
    const errors = validateEntryRow({ ...validRow, in_time: "25:00" });
    expect(errors.in_time).toBeTruthy();
  });

  it("rejects an unknown status", () => {
    const errors = validateEntryRow({ ...validRow, status: "closed" as never });
    expect(errors.status).toBeTruthy();
  });

  it("treats empty strings as null", () => {
    const errors = validateEntryRow({ ...validRow, model: "", remarks: "" });
    expect(errors).toEqual({});
    const payload = rowToEntryCreate({ ...validRow, model: "", remarks: "" }, 1, 2);
    expect(payload.model).toBeNull();
    expect(payload.remarks).toBeNull();
    expect(payload.sr_no).toBe(2);
  });
});
