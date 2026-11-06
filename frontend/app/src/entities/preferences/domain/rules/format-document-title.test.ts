import { describe, expect, test } from "vitest";

import { formatDocumentTitle } from "@/entities/preferences/domain/rules/format-document-title";

describe("formatDocumentTitle", () => {
  test.each([
    { name: "a label", label: "QA", expected: "QA · Schema" },
    { name: "a label with surrounding spaces", label: " QA ", expected: "QA · Schema" },
    { name: "a null label", label: null, expected: "Schema" },
    { name: "an empty label", label: "", expected: "Schema" },
    { name: "a whitespace-only label", label: "   ", expected: "Schema" },
  ])("composes the tab title from $name", ({ label, expected }) => {
    expect(formatDocumentTitle(label, "Schema")).toBe(expected);
  });
});
