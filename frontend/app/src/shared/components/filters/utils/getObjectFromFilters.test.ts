import { describe, expect, it } from "vitest";

import { getObjectFromFilters } from "@/shared/components/filters/utils/getObjectFromFilters";
import type { Filter } from "@/shared/hooks/useFilters";

import type { ModelSchema } from "@/entities/schema/types";

import { generateRelationshipSchema } from "../../../../../tests/fake/schema";

describe("getObjectFromFilters - test", () => {
  it("returns value for a attribute correctly", () => {
    // GIVEN
    const filters: Array<Filter> = [{ name: "field1__value", value: "value1" }];

    // WHEN
    const objectData = getObjectFromFilters({} as any, filters);

    // THEN
    expect(objectData).toEqual({
      field1: { value: "value1" },
    });
  });

  it("returns value for an attribute of kind list correctly", () => {
    // GIVEN
    const filters: Array<Filter> = [{ name: "field1__values", value: ["value1"] }];

    // WHEN
    const objectData = getObjectFromFilters({} as any, filters);

    // THEN
    expect(objectData).toEqual({
      field1: { value: ["value1"] },
    });
  });

  it("returns value for a relationship of cardinality one correctly", () => {
    // GIVEN
    const filters: Array<Filter> = [
      {
        name: "relationship1__ids",
        value: [{ id: "id1", display_label: "relationship1", __typename: "peer1" }],
      },
    ];
    const schema = {
      relationships: [
        generateRelationshipSchema({ name: "relationship1", cardinality: "one", peer: "peer1" }),
      ],
    } as ModelSchema;

    // WHEN
    const objectData = getObjectFromFilters(schema, filters);

    // THEN
    expect(objectData).toEqual({
      relationship1: { node: { id: "id1", display_label: "relationship1", __typename: "peer1" } },
    });
  });

  it("returns value for a relationship of cardinality many correctly", () => {
    // GIVEN
    const filters: Array<Filter> = [
      {
        name: "relationship1__ids",
        value: [{ id: "id1", display_label: "label1", __typename: "peer1" }],
      },
    ];
    const schema = {
      relationships: [
        generateRelationshipSchema({ name: "relationship1", cardinality: "many", peer: "peer1" }),
      ],
    } as ModelSchema;

    // WHEN
    const objectData = getObjectFromFilters(schema, filters);

    // THEN
    expect(objectData).toEqual({
      relationship1: {
        edges: [{ node: { id: "id1", display_label: "label1", __typename: "peer1" } }],
      },
    });
  });
});
