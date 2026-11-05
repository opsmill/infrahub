import { describe, expect, test } from "vitest";

import {
  instanceLabelError,
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

describe("instanceLabelError", () => {
  test.each([
    { name: "a short label", value: "QA" },
    { name: "an empty label", value: "" },
    { name: "a label of exactly 32 characters", value: "a".repeat(32) },
    { name: "a label whose padding pushes it past 32 characters", value: ` ${"a".repeat(32)} ` },
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
  ])("rejects a label containing $name", ({ value }) => {
    // GIVEN a label with a line break
    const input = value;

    // WHEN validated
    const error = instanceLabelError(input);

    // THEN the message names the rule
    expect(error).toBe("The instance label cannot contain a line break.");
  });
});
