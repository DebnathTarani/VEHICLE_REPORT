import { describe, expect, it } from "vitest";
import { formatVrn, isValidVrn, normalizeVrnRaw, vrnToNormalized } from "./vrn";

describe("formatVrn", () => {
  it("formats a plain alphanumeric VRN into the dashed display form", () => {
    expect(formatVrn("as01ab1234")).toBe("AS-01-AB-1234");
  });

  it("strips non-alphanumeric characters and re-formats", () => {
    expect(formatVrn("as-01 ab/12*34")).toBe("AS-01-AB-1234");
  });

  it("is idempotent on already-formatted values", () => {
    expect(formatVrn(formatVrn("AS-01-AB-1234"))).toBe("AS-01-AB-1234");
  });

  it("handles 1-3 digit state code and 1-4 letter series", () => {
    expect(formatVrn("DL1C1234")).toBe("DL-1-C-1234");
    expect(formatVrn("MH12ABCD999")).toBe("MH-12-ABCD-999");
  });

  it("returns stripped uppercase for non-matching input", () => {
    expect(formatVrn("abc")).toBe("ABC");
    expect(formatVrn("1234")).toBe("1234");
  });
});

describe("isValidVrn", () => {
  it("accepts dashed and plain forms", () => {
    expect(isValidVrn("AS-01-AB-1234")).toBe(true);
    expect(isValidVrn("as01ab1234")).toBe(true);
  });

  it("rejects malformed values", () => {
    expect(isValidVrn("A-01-AB-1234")).toBe(false);
    expect(isValidVrn("AS-1234-AB")).toBe(false);
    expect(isValidVrn("")).toBe(false);
    expect(isValidVrn("A1B2")).toBe(false);
  });
});

describe("normalizeVrnRaw / vrnToNormalized", () => {
  it("strips separators and uppercases", () => {
    expect(normalizeVrnRaw(" as-01/ab 1234 ")).toBe("AS01AB1234");
    expect(vrnToNormalized("AS-01-AB-1234")).toBe("AS01AB1234");
  });
});
