import { describe, expect, it } from "vitest";

import type { ColumnVisibilityState } from "@/entities/nodes/columns/domain/model/column-visibility-state";
import {
  OBJECT_COLUMN_SURFACE,
  RELATIONSHIP_COLUMN_SURFACE,
} from "@/entities/nodes/columns/domain/rules/column-surfaces";
import {
  type ColumnCandidate,
  getColumnCandidates,
} from "@/entities/nodes/columns/domain/rules/get-column-candidates";
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

/** The columns actually on screen: the state's departures applied on top of the surface's defaults. */
const getVisibleNames = (state: ColumnVisibilityState, columnCandidates: ColumnCandidate[]) =>
  columnCandidates
    .filter(({ name, isDefaultVisible }) => state[name] ?? isDefaultVisible)
    .map(({ name }) => name);

describe("getColumnVisibilityState", () => {
  it("returns an empty state when both params are absent", () => {
    // GIVEN
    const columnCandidates = getColumnCandidates(generateSchema(), OBJECT_COLUMN_SURFACE);

    // WHEN
    const state = getColumnVisibilityState([], [], columnCandidates);

    // THEN
    expect(state).toEqual({});
  });

  it("hides a field that is visible by default", () => {
    // GIVEN
    const columnCandidates = getColumnCandidates(generateSchema(), OBJECT_COLUMN_SURFACE);

    // WHEN
    const state = getColumnVisibilityState(["description"], [], columnCandidates);

    // THEN
    expect(state).toEqual({ description: false });
  });

  it("reveals a field that is hidden by default", () => {
    // GIVEN
    const columnCandidates = getColumnCandidates(generateSchema(), OBJECT_COLUMN_SURFACE);

    // WHEN
    const state = getColumnVisibilityState([], ["internal_note"], columnCandidates);

    // THEN
    expect(state).toEqual({ internal_note: true });
  });

  it("drops names the surface does not offer", () => {
    // GIVEN
    const columnCandidates = getColumnCandidates(generateSchema(), OBJECT_COLUMN_SURFACE);
    const hiddenNames = ["gone_from_this_schema", "id", "", "description"];

    // WHEN
    const state = getColumnVisibilityState(hiddenNames, ["also_gone"], columnCandidates);

    // THEN
    expect(state).toEqual({ description: false });
  });

  it("drops a hidden name for a field that is already hidden by default", () => {
    // GIVEN
    const columnCandidates = getColumnCandidates(generateSchema(), OBJECT_COLUMN_SURFACE);

    // WHEN
    const state = getColumnVisibilityState(["internal_note"], [], columnCandidates);

    // THEN
    expect(state).toEqual({});
  });

  it("drops a shown name for a field that is already visible by default", () => {
    // GIVEN
    const columnCandidates = getColumnCandidates(generateSchema(), OBJECT_COLUMN_SURFACE);

    // WHEN
    const state = getColumnVisibilityState([], ["description"], columnCandidates);

    // THEN
    expect(state).toEqual({});
  });

  it("dedupes a name repeated within one param", () => {
    // GIVEN
    const columnCandidates = getColumnCandidates(generateSchema(), OBJECT_COLUMN_SURFACE);

    // WHEN
    const state = getColumnVisibilityState(
      ["description", "description"],
      ["internal_note", "internal_note"],
      columnCandidates
    );

    // THEN
    expect(state).toEqual({ description: false, internal_note: true });
  });

  it("lets hiding win over revealing when both params name the same field", () => {
    // GIVEN
    const columnCandidates = getColumnCandidates(generateSchema(), OBJECT_COLUMN_SURFACE);
    const contradictedNames = ["description", "internal_note"];

    // WHEN
    const state = getColumnVisibilityState(contradictedNames, contradictedNames, columnCandidates);

    // THEN
    // `internal_note` gets no entry at all, so it stays at its default — hidden.
    expect(state).toEqual({ description: false });
  });

  it("drops a shown name on a surface that cannot reveal, and reveals nothing there", () => {
    // GIVEN
    const columnCandidates = getColumnCandidates(generateSchema(), RELATIONSHIP_COLUMN_SURFACE);

    // WHEN
    const state = getColumnVisibilityState(["description"], ["internal_note"], columnCandidates);
    const revealed = getRevealedFields(state);

    // THEN
    expect({ state, revealed }).toEqual({ state: { description: false }, revealed: [] });
  });

  it("keeps the first column visible when the hide list names every column", () => {
    // GIVEN
    const columnCandidates = getColumnCandidates(generateSchema(), OBJECT_COLUMN_SURFACE);
    const everyColumnName = columnCandidates.map((field) => field.name);

    // WHEN
    const state = getColumnVisibilityState(everyColumnName, [], columnCandidates);

    // THEN
    // The survivor is the first column in display order; every other hide request is kept.
    expect(getVisibleNames(state, columnCandidates)).toEqual(["name"]);
  });

  // The picker greys out the last remaining item, so the only way to ask for an empty table is by
  // hand — an edited or stale link. Junk, duplicates and a contradicting show list get it no further.
  it("keeps a column visible when a crafted url hides every one of them", () => {
    // GIVEN
    const columnCandidates = getColumnCandidates(generateSchema(), OBJECT_COLUMN_SURFACE);
    const everyColumnName = columnCandidates.map((field) => field.name);
    const craftedHiddenNames = [...everyColumnName, "gone_from_this_schema", "name"];

    // WHEN
    const state = getColumnVisibilityState(craftedHiddenNames, everyColumnName, columnCandidates);

    // THEN
    expect(getVisibleNames(state, columnCandidates)).toEqual(["name"]);
  });
});

describe("getRevealedFields", () => {
  it("returns the revealed names sorted, so param order cannot change the value", () => {
    // GIVEN
    const columnCandidates = getColumnCandidates(generateSchema(), OBJECT_COLUMN_SURFACE);
    const noteOrders = [
      ["owner_note", "internal_note"],
      ["internal_note", "owner_note"],
    ];

    // WHEN
    const revealedLists = noteOrders.map((shownNames) =>
      getRevealedFields(getColumnVisibilityState([], shownNames, columnCandidates))
    );

    // THEN
    expect(revealedLists).toEqual([
      ["internal_note", "owner_note"],
      ["internal_note", "owner_note"],
    ]);
  });

  it("ignores default-visible and unknown fields", () => {
    // GIVEN
    const columnCandidates = getColumnCandidates(generateSchema(), OBJECT_COLUMN_SURFACE);
    const shownNames = ["description", "gone_from_this_schema", "internal_note"];

    // WHEN
    const revealed = getRevealedFields(getColumnVisibilityState([], shownNames, columnCandidates));

    // THEN
    expect(revealed).toEqual(["internal_note"]);
  });

  it("reveals nothing a hidden name contradicts, without the caller re-applying the rule", () => {
    // GIVEN
    const columnCandidates = getColumnCandidates(generateSchema(), OBJECT_COLUMN_SURFACE);
    const contradictedNames = ["internal_note"];

    // WHEN
    const revealed = getRevealedFields(
      getColumnVisibilityState(
        contradictedNames,
        [...contradictedNames, "owner_note"],
        columnCandidates
      )
    );

    // THEN
    expect(revealed).toEqual(["owner_note"]);
  });
});
