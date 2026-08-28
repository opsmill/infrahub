import { describe, expect, it } from "vitest";

import {
  OBJECT_COLUMN_SURFACE,
  RELATIONSHIP_COLUMN_SURFACE,
} from "@/entities/nodes/columns/domain/model/column-surface";
import { getColumnFields } from "@/entities/nodes/columns/domain/rules/get-column-fields";
import {
  getColumnVisibilityState,
  getRevealedFields,
} from "@/entities/nodes/columns/domain/rules/get-column-visibility-state";

import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../tests/fake/schema";

const generateSchema = () =>
  generateNodeSchema({
    attributes: [
      generateAttributeSchema({ name: "name", kind: "Text" }),
      generateAttributeSchema({ name: "description", kind: "Text" }),
      generateAttributeSchema({ name: "internal_note", kind: "Text", display: "extra" }),
      generateAttributeSchema({ name: "owner_note", kind: "Text", display: "extra" }),
      generateAttributeSchema({ name: "id", kind: "Text" }),
    ],
    relationships: [
      generateRelationshipSchema({ name: "site", kind: "Attribute", cardinality: "one" }),
    ],
  });

describe("getColumnVisibilityState", () => {
  it("returns an empty state when both params are absent", () => {
    // GIVEN
    const columnFields = getColumnFields(generateSchema(), OBJECT_COLUMN_SURFACE);

    // WHEN
    const state = getColumnVisibilityState([], [], columnFields);

    // THEN
    expect(state).toEqual({});
  });

  it("hides a field that is visible by default", () => {
    // GIVEN
    const columnFields = getColumnFields(generateSchema(), OBJECT_COLUMN_SURFACE);

    // WHEN
    const state = getColumnVisibilityState(["description"], [], columnFields);

    // THEN
    expect(state).toEqual({ description: false });
  });

  it("reveals a field that is hidden by default", () => {
    // GIVEN
    const columnFields = getColumnFields(generateSchema(), OBJECT_COLUMN_SURFACE);

    // WHEN
    const state = getColumnVisibilityState([], ["internal_note"], columnFields);

    // THEN
    expect(state).toEqual({ internal_note: true });
  });

  it("drops names the surface does not offer", () => {
    // GIVEN
    const columnFields = getColumnFields(generateSchema(), OBJECT_COLUMN_SURFACE);
    const hiddenNames = ["gone_from_this_schema", "id", "", "description"];

    // WHEN
    const state = getColumnVisibilityState(hiddenNames, ["also_gone"], columnFields);

    // THEN
    expect(state).toEqual({ description: false });
  });

  it("drops a hidden name for a field that is already hidden by default", () => {
    // GIVEN
    const columnFields = getColumnFields(generateSchema(), OBJECT_COLUMN_SURFACE);

    // WHEN
    const state = getColumnVisibilityState(["internal_note"], [], columnFields);

    // THEN
    expect(state).toEqual({});
  });

  it("drops a shown name for a field that is already visible by default", () => {
    // GIVEN
    const columnFields = getColumnFields(generateSchema(), OBJECT_COLUMN_SURFACE);

    // WHEN
    const state = getColumnVisibilityState([], ["description"], columnFields);

    // THEN
    expect(state).toEqual({});
  });

  it("dedupes a name repeated within one param", () => {
    // GIVEN
    const columnFields = getColumnFields(generateSchema(), OBJECT_COLUMN_SURFACE);

    // WHEN
    const state = getColumnVisibilityState(
      ["description", "description"],
      ["internal_note", "internal_note"],
      columnFields
    );

    // THEN
    expect(state).toEqual({ description: false, internal_note: true });
  });

  it("lets hiding win over revealing when both params name the same field", () => {
    // GIVEN
    const columnFields = getColumnFields(generateSchema(), OBJECT_COLUMN_SURFACE);
    const contradictedNames = ["description", "internal_note"];

    // WHEN
    const state = getColumnVisibilityState(contradictedNames, contradictedNames, columnFields);

    // THEN
    // `internal_note` gets no entry at all, so it stays at its default — hidden.
    expect(state).toEqual({ description: false });
  });

  it("drops a shown name on a surface that cannot reveal, and reveals nothing there", () => {
    // GIVEN
    const columnFields = getColumnFields(generateSchema(), RELATIONSHIP_COLUMN_SURFACE);

    // WHEN
    const state = getColumnVisibilityState(["description"], ["internal_note"], columnFields);
    const revealed = getRevealedFields(["internal_note"], columnFields);

    // THEN
    expect({ state, revealed }).toEqual({ state: { description: false }, revealed: [] });
  });
});

describe("getRevealedFields", () => {
  it("returns the revealed names sorted, so param order cannot change the value", () => {
    // GIVEN
    const columnFields = getColumnFields(generateSchema(), OBJECT_COLUMN_SURFACE);
    const noteOrders = [
      ["owner_note", "internal_note"],
      ["internal_note", "owner_note"],
    ];

    // WHEN
    const revealedLists = noteOrders.map((shownNames) =>
      getRevealedFields(shownNames, columnFields)
    );

    // THEN
    expect(revealedLists).toEqual([
      ["internal_note", "owner_note"],
      ["internal_note", "owner_note"],
    ]);
  });

  it("ignores default-visible and unknown fields", () => {
    // GIVEN
    const columnFields = getColumnFields(generateSchema(), OBJECT_COLUMN_SURFACE);
    const shownNames = ["description", "gone_from_this_schema", "internal_note"];

    // WHEN
    const revealed = getRevealedFields(shownNames, columnFields);

    // THEN
    expect(revealed).toEqual(["internal_note"]);
  });
});
