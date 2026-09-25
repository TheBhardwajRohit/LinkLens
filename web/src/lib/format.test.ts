import { describe, expect, it } from "vitest";

import { daysSince, formatAge, formatDate, isRedacted } from "./format";

describe("format", () => {
  it("formats dates in UTC", () => {
    expect(formatDate("2007-10-09T18:20:50+00:00")).toBe("9 Oct 2007");
    expect(formatDate(null)).toBeNull();
    expect(formatDate("not a date")).toBeNull();
  });

  it("describes ages in plain words", () => {
    expect(formatAge(0)).toBe("less than a day");
    expect(formatAge(3)).toBe("3 days");
    expect(formatAge(150)).toBe("5 months");
    expect(formatAge(6925)).toBe("18 years");
    expect(formatAge(null)).toBeNull();
  });

  it("counts days since a date", () => {
    expect(daysSince("2026-09-20T00:00:00Z", Date.parse("2026-09-25T12:00:00Z"))).toBe(5);
  });

  it("spots hidden registrant names", () => {
    expect(isRedacted("REDACTED FOR PRIVACY")).toBe(true);
    expect(isRedacted("Data Protected")).toBe(true);
    expect(isRedacted("GitHub, Inc.")).toBe(false);
    expect(isRedacted(null)).toBe(false);
  });
});
