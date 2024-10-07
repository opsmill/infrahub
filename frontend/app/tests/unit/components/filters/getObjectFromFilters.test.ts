import { getObjectFromFilters } from "@/components/filters/utils/getObjectFromFilters";
import { Filter } from "@/hooks/useFilters";
import { IModelSchema } from "@/state/atoms/schema.atom";
import { describe, expect } from "vitest";
import { buildRelationshipSchema } from "../form/utils/getFormFieldsFromSchema.test";

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

  it("returns value for a relationship of cardinality one correctly", () => {
    // GIVEN
    const filters: Array<Filter> = [{ name: "relationship1__ids", value: ["id1"] }];
    const schema = {
      relationships: [
        buildRelationshipSchema({ name: "relationship1", cardinality: "one", peer: "peer1" }),
      ],
    } as IModelSchema;

    // WHEN
    const objectData = getObjectFromFilters(schema, filters);

    // THEN
    expect(objectData).toEqual({
      relationship1: { node: { id: "id1", display_label: "", __typename: "peer1" } },
    });
  });

  it("returns value for a relationship of cardinality many correctly", () => {
    // GIVEN
    const filters: Array<Filter> = [{ name: "relationship1__ids", value: ["id1"] }];
    const schema = {
      relationships: [
        buildRelationshipSchema({ name: "relationship1", cardinality: "many", peer: "peer1" }),
      ],
    } as IModelSchema;

    // WHEN
    const objectData = getObjectFromFilters(schema, filters);

    // THEN
    expect(objectData).toEqual({
      relationship1: { edges: [{ node: { id: "id1", display_label: "", __typename: "peer1" } }] },
    });
  });
});
