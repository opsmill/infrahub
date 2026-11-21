import { describe, expect, it } from "vitest";

import type { ListElement } from "@/entities/nodes/object/domain/model/list-element";

import { filterListElements } from "./filter-list-elements";

const elements: ListElement[] = [
  { position: 1, value: "Ethernet1/1", type: "Text", text: "Ethernet1/1" },
  { position: 2, value: "Ethernet2/1", type: "Text", text: "Ethernet2/1" },
  {
    position: 3,
    value: { id: "18e5-1", __typename: "BuiltinTag", display_label: "blue" },
    type: "Node",
    text: "blue",
  },
];

describe("filterListElements", () => {
  it("should return every element for an empty query", () => {
    // WHEN
    const result = filterListElements(elements, "  ");

    // THEN
    expect(result).toBe(elements);
  });

  it("should match the displayed text, ignoring case", () => {
    // WHEN
    const result = filterListElements(elements, "ETHERNET2");

    // THEN
    expect(result.map((element) => element.position)).toEqual([2]);
  });

  it("should match a node reference by its kind", () => {
    // WHEN
    const result = filterListElements(elements, "builtintag");

    // THEN
    expect(result.map((element) => element.position)).toEqual([3]);
  });

  it("should not match a node reference by its id", () => {
    // WHEN
    const result = filterListElements(elements, "18e5");

    // THEN
    expect(result).toEqual([]);
  });
});
