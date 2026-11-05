import { describe, expect, test } from "vitest";

import { formatDocumentTitle } from "@/entities/preferences/domain/rules/format-document-title";

describe("formatDocumentTitle", () => {
  test.each([
    { name: "a label and a page title", label: "QA", pageTitle: "Schema", expected: "QA · Schema" },
    {
      name: "a label and the app name",
      label: "QA",
      pageTitle: "Infrahub",
      expected: "QA · Infrahub",
    },
    { name: "a null label", label: null, pageTitle: "Schema", expected: "Schema" },
    { name: "an undefined label", label: undefined, pageTitle: "Schema", expected: "Schema" },
    { name: "an empty label", label: "", pageTitle: "Schema", expected: "Schema" },
    { name: "a whitespace-only label", label: "   ", pageTitle: "Schema", expected: "Schema" },
    {
      name: "a label with surrounding spaces",
      label: " QA ",
      pageTitle: "Schema",
      expected: "QA · Schema",
    },
  ])("composes the tab title from $name", ({ label, pageTitle, expected }) => {
    // GIVEN a label and a page title
    const input = { label, pageTitle };

    // WHEN the document title is composed
    const title = formatDocumentTitle(input.label, input.pageTitle);

    // THEN it carries the label only when one is set
    expect(title).toBe(expected);
  });
});
