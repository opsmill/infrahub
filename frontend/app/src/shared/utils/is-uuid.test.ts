import { describe, expect, test } from "vitest";

import { isUuid } from "./is-uuid";

describe("isUuid", () => {
  test("accepts a canonical lowercase v4 UUID", () => {
    expect(isUuid("17a4cdef-1234-4abc-8def-0123456789ab")).toBe(true);
  });

  test("accepts mixed-case", () => {
    expect(isUuid("17A4CDEF-1234-4abc-8DEF-0123456789AB")).toBe(true);
  });

  test("trims surrounding whitespace", () => {
    expect(isUuid("  17a4cdef-1234-4abc-8def-0123456789ab \n")).toBe(true);
  });

  test("rejects empty string", () => {
    expect(isUuid("")).toBe(false);
  });

  test("rejects missing dashes", () => {
    expect(isUuid("17a4cdef12344abc8def0123456789ab")).toBe(false);
  });

  test("rejects extra characters", () => {
    expect(isUuid("foo-17a4cdef-1234-4abc-8def-0123456789ab")).toBe(false);
    expect(isUuid("17a4cdef-1234-4abc-8def-0123456789ab-bar")).toBe(false);
  });

  test("rejects partial UUID", () => {
    expect(isUuid("17a4cdef-1234")).toBe(false);
  });

  test("rejects non-hex characters", () => {
    expect(isUuid("zzzzzzzz-1234-4abc-8def-0123456789ab")).toBe(false);
  });
});
