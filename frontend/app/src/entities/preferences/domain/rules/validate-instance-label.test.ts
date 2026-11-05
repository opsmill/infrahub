import { describe, expect, test } from "vitest";

import {
  instanceLabelError,
  instanceLabelLength,
  normalizeInstanceLabel,
} from "@/entities/preferences/domain/rules/validate-instance-label";

describe("normalizeInstanceLabel", () => {
  test("trims surrounding whitespace", () => {
    // GIVEN a label with surrounding spaces
    const value = "  Production  ";

    // WHEN normalized
    const normalized = normalizeInstanceLabel(value);

    // THEN only the text remains
    expect(normalized).toBe("Production");
  });

  test.each([
    { name: "an empty string", value: "" },
    { name: "whitespace only", value: "   " },
  ])("turns $name into null so the label is cleared", ({ value }) => {
    // GIVEN a label without text
    const input = value;

    // WHEN normalized
    const normalized = normalizeInstanceLabel(input);

    // THEN it is null
    expect(normalized).toBeNull();
  });
});

describe("instanceLabelLength", () => {
  test.each([
    { name: "an ASCII label", value: "QA", expected: 2 },
    { name: "a padded label", value: "  QA  ", expected: 2 },
    { name: "an accented label", value: "Zürich", expected: 6 },
    { name: "an emoji, which is two UTF-16 units", value: "😀", expected: 1 },
  ])("counts $name in code points", ({ value, expected }) => {
    // GIVEN a label
    const input = value;

    // WHEN its length is counted
    const length = instanceLabelLength(input);

    // THEN each code point counts once
    expect(length).toBe(expected);
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
  ])("accepts $name", ({ value }) => {
    // GIVEN a valid label
    const input = value;

    // WHEN validated
    const error = instanceLabelError(input);

    // THEN there is no error
    expect(error).toBeNull();
  });

  test("rejects a label longer than 32 characters with a message naming the limit", () => {
    // GIVEN a 33-character label
    const value = "a".repeat(33);

    // WHEN validated
    const error = instanceLabelError(value);

    // THEN the message names the limit
    expect(error).toBe("The instance label cannot be longer than 32 characters.");
  });

  test.each([
    { name: "a line feed", value: "QA\nstaging" },
    { name: "a carriage return", value: "QA\rstaging" },
    { name: "a tab", value: "QA\tstaging" },
    { name: "a NUL character", value: "QA\u0000staging" },
    { name: "a right-to-left override", value: "QA‮staging" },
    { name: "an isolate terminator", value: "QA⁩staging" },
  ])("rejects a label containing $name", ({ value }) => {
    // GIVEN a label with a control character
    const input = value;

    // WHEN validated
    const error = instanceLabelError(input);

    // THEN the message names the rule
    expect(error).toBe("The instance label cannot contain control characters.");
  });
});
