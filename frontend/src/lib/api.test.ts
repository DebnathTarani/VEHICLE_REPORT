import { describe, expect, it } from "vitest";
import { buildQuery } from "./api";

describe("buildQuery", () => {
  it("returns empty string when no usable params", () => {
    expect(buildQuery({})).toBe("");
    expect(buildQuery({ a: undefined, b: null, c: "" })).toBe("");
  });

  it("builds a ?-prefixed querystring", () => {
    expect(buildQuery({ location_id: 3, page: 2 })).toBe("?location_id=3&page=2");
  });

  it("skips null, undefined and empty values", () => {
    expect(buildQuery({ q: "AB 12", status: null, page: 1 })).toBe(
      "?q=AB+12&page=1",
    );
  });

  it("encodes special characters", () => {
    expect(buildQuery({ q: "a&b=c" })).toBe("?q=a%26b%3Dc");
  });

  it("stringifies booleans and numbers", () => {
    expect(buildQuery({ flag: true, n: 0 })).toBe("?flag=true&n=0");
  });
});
