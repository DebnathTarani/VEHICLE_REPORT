import { describe, expect, it } from "vitest";
import { formatDate, formatTime } from "./dates";

describe("formatDate", () => {
  it("renders DD-MM-YYYY by default", () => {
    expect(formatDate("2026-11-15")).toBe("15-11-2026");
  });

  it("handles ISO datetimes by taking the date part", () => {
    expect(formatDate("2026-01-05T09:30:00Z")).toBe("05-01-2026");
  });

  it("supports alternate token formats", () => {
    const slash = String.fromCharCode(47);
    expect(formatDate("2026-11-15", "YYYY" + slash + "MM" + slash + "DD")).toBe(["2026", "11", "15"].join(slash));
    expect(formatDate("2026-11-15", "DD" + slash + "MM" + slash + "YYYY")).toBe(["15", "11", "2026"].join(slash));
  });

  it("returns empty string for null/undefined/empty", () => {
    expect(formatDate(null)).toBe("");
    expect(formatDate(undefined)).toBe("");
    expect(formatDate("")).toBe("");
  });

  it("returns raw value when unparseable", () => {
    expect(formatDate("not-a-date")).toBe("not-a-date");
  });
});

describe("formatTime", () => {
  it("extracts 24h HH:MM from datetimes and plain times", () => {
    expect(formatTime("2026-11-15T09:05:00")).toBe("09:05");
    expect(formatTime("14:30")).toBe("14:30");
    expect(formatTime(null)).toBe("");
  });
});
