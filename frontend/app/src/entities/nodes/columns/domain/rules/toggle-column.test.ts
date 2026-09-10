import { describe, expect, it } from "vitest";

import { hideColumn, toggleColumn } from "@/entities/nodes/columns/domain/rules/toggle-column";

describe("toggleColumn", () => {
  it("names a field that is visible by default in the hidden list", () => {
    // GIVEN
    const hidden: string[] = [];
    const shown: string[] = [];

    // WHEN
    const next = toggleColumn(hidden, shown, "description", true);

    // THEN
    expect(next).toEqual({ hidden: ["description"], shown: [] });
  });

  it("empties both lists when a hidden default-visible field is shown again", () => {
    // GIVEN
    const hidden = ["description"];
    const shown: string[] = [];

    // WHEN
    const next = toggleColumn(hidden, shown, "description", true);

    // THEN
    expect(next).toEqual({ hidden: [], shown: [] });
  });

  it("names a field that is hidden by default in the shown list", () => {
    // GIVEN
    const hidden: string[] = [];
    const shown: string[] = [];

    // WHEN
    const next = toggleColumn(hidden, shown, "internal_note", false);

    // THEN
    expect(next).toEqual({ hidden: [], shown: ["internal_note"] });
  });

  it("empties both lists when a revealed default-hidden field is hidden again", () => {
    // GIVEN
    const hidden: string[] = [];
    const shown = ["internal_note"];

    // WHEN
    const next = toggleColumn(hidden, shown, "internal_note", false);

    // THEN
    expect(next).toEqual({ hidden: [], shown: [] });
  });

  it("leaves the other names in both lists untouched", () => {
    // GIVEN
    const hidden = ["description"];
    const shown = ["internal_note", "owner_note"];

    // WHEN
    const next = toggleColumn(hidden, shown, "internal_note", false);

    // THEN
    expect(next).toEqual({ hidden: ["description"], shown: ["owner_note"] });
  });
});

describe("hideColumn", () => {
  it("appends a field neither list mentions to the hidden list", () => {
    // GIVEN
    const hidden: string[] = [];
    const shown = ["internal_note"];

    // WHEN
    const next = hideColumn(hidden, shown, "description");

    // THEN
    expect(next).toEqual({ hidden: ["description"], shown: ["internal_note"] });
  });

  it("drops a revealed field from the shown list instead of hiding it twice", () => {
    // GIVEN
    const hidden = ["description"];
    const shown = ["internal_note"];

    // WHEN
    const next = hideColumn(hidden, shown, "internal_note");

    // THEN
    expect(next).toEqual({ hidden: ["description"], shown: [] });
  });

  it("stays idempotent for a field the hidden list already names", () => {
    // GIVEN
    const hidden = ["description"];
    const shown: string[] = [];

    // WHEN
    const next = hideColumn(hidden, shown, "description");

    // THEN
    expect(next).toEqual({ hidden: ["description"], shown: [] });
  });
});
