import { describe, expect, test } from "vitest";

import {
  instanceLabelError,
  instanceLabelLength,
  normalizeInstanceLabel,
} from "@/entities/preferences/domain/rules/validate-instance-label";

describe("normalizeInstanceLabel", () => {
  test.each([
    { name: "a padded label", value: "  Production  ", expected: "Production" },
    { name: "an empty string", value: "", expected: null },
    { name: "whitespace only", value: "   ", expected: null },
  ])("normalizes $name", ({ value, expected }) => {
    expect(normalizeInstanceLabel(value)).toBe(expected);
  });
});

describe("instanceLabelLength", () => {
  test.each([
    { name: "an ASCII label", value: "QA", expected: 2 },
    { name: "a padded label", value: "  QA  ", expected: 2 },
    { name: "an accented label", value: "Zürich", expected: 6 },
    { name: "an emoji, which is two UTF-16 units", value: "😀", expected: 1 },
  ])("counts $name in code points", ({ value, expected }) => {
    expect(instanceLabelLength(value)).toBe(expected);
  });
});

describe("instanceLabelError", () => {
  test.each([
    { name: "a short label", value: "QA" },
    { name: "an empty label", value: "" },
    { name: "a label of exactly 32 characters", value: "a".repeat(32) },
    { name: "a label whose padding pushes it past 32 characters", value: ` ${"a".repeat(32)} ` },
    { name: "a label with a non-ASCII letter", value: "Zürich PROD" },
    { name: "a label with an emoji", value: "PROD 🚀" },
    { name: "a label of 32 astral characters", value: "😀".repeat(32) },
    { name: "a label with a trailing tab, which the server removes", value: "QA\t" },
    { name: "a label with a leading line break, which the server removes", value: "\nQA" },
    { name: "a lowercase null", value: "null" },
  ])("accepts $name", ({ value }) => {
    expect(instanceLabelError(value)).toBeNull();
  });

  test("rejects a label longer than 32 characters with a message naming the limit", () => {
    expect(instanceLabelError("a".repeat(33))).toBe(
      "The instance label cannot be longer than 32 characters."
    );
  });

  test("rejects the label NULL, which reads back as an unset value", () => {
    expect(instanceLabelError(" NULL ")).toBe(
      'The instance label cannot be "NULL", which marks an unset value.'
    );
  });

  test.each([
    { name: "a line feed", value: "QA\nstaging" },
    { name: "a tab", value: "Q\tA" },
    { name: "a Unicode line separator", value: "QA\u2028staging" },
    { name: "a Unicode paragraph separator", value: "QA\u2029staging" },
    { name: "a right-to-left override", value: "QA\u202Estaging" },
    { name: "an isolate terminator", value: "QA\u2069staging" },
    { name: "a right-to-left mark", value: "QA\u200Fstaging" },
  ])("rejects a label containing $name", ({ value }) => {
    expect(instanceLabelError(value)).toBe("The instance label cannot contain control characters.");
  });
});
