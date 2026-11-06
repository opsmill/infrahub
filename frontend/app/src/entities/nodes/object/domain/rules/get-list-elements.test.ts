import { describe, expect, it } from "vitest";

import { getListElements } from "./get-list-elements";

describe("getListElements", () => {
  it("should give each element its 1-based position, type and text", () => {
    // GIVEN
    const values = ["spine", 9214, true, null, { ip: "10.0.0.1" }, ["a", "b"]];

    // WHEN
    const result = getListElements(values);

    // THEN
    expect(result.map(({ position, type, text }) => ({ position, type, text }))).toEqual([
      { position: 1, type: "Text", text: "spine" },
      { position: 2, type: "Number", text: "9214" },
      { position: 3, type: "Boolean", text: "true" },
      { position: 4, type: "Null", text: "null" },
      { position: 5, type: "Object", text: '{"ip":"10.0.0.1"}' },
      { position: 6, type: "Array", text: '["a","b"]' },
    ]);
  });

  it("should type a node reference as Node", () => {
    // GIVEN
    const values = [{ id: "18e5-1", __typename: "BuiltinTag", display_label: "blue" }];

    // WHEN
    const result = getListElements(values);

    // THEN
    expect(result[0]?.type).toBe("Node");
  });
});
