import { getRelationshipDefaultValue } from "@/components/form/utils/getRelationshipDefaultValue";
import { RESOURCE_GENERIC_KIND } from "@/screens/resource-manager/constants";
import { RelationshipManyType, RelationshipOneType } from "@/utils/getObjectItemDisplayValue";
import { describe, expect, vi } from "vitest";

const buildRelationshipOneData = (override: Partial<RelationshipOneType>): RelationshipOneType => ({
  node: {
    id: "relationship-one-id",
    display_label: "Relationship One",
    __typename: "RelationshipOne",
  },
  properties: {
    updated_at: "2024-07-17T17:59:05.309135+00:00",
    is_protected: null,
    is_visible: true,
    source: null,
    owner: null,
    __typename: "RelationshipProperty",
  },
  ...override,
});

describe("getRelationshipDefaultValue", () => {
  describe("when cardinality one", () => {
    it("returns null if there is no relationship", () => {
      // GIVEN
      const relationshipData = undefined;

      // WHEN
      const defaultValue = getRelationshipDefaultValue({ relationshipData });

      // THEN
      expect(defaultValue).to.deep.equal({ source: null, value: null });
    });

    it("returns user defined relationship", () => {
      // GIVEN
      const relationshipData = buildRelationshipOneData({ properties: { source: null } });

      // WHEN
      const defaultValue = getRelationshipDefaultValue({ relationshipData });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: { type: "user" },
        value: {
          id: "relationship-one-id",
          display_label: "Relationship One",
          __typename: "RelationshipOne",
        },
      });
    });

    it("returns relationship from pool", () => {
      // GIVEN
      vi.mock("jotai", () => ({
        atom: vi.fn(),
        createStore: () => ({
          get: () => [{ kind: "FakeResourcePool", inherit_from: [RESOURCE_GENERIC_KIND] }],
        }),
      }));

      const relationshipData = buildRelationshipOneData({
        properties: {
          source: {
            id: "pool-random-id",
            display_label: "test name pool",
            __typename: "FakeResourcePool",
          },
        },
      });

      // WHEN
      const defaultValue = getRelationshipDefaultValue({ relationshipData });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          type: "pool",
          label: "test name pool",
          id: "pool-random-id",
          kind: "FakeResourcePool",
        },
        value: {
          id: "relationship-one-id",
          display_label: "Relationship One",
          __typename: "RelationshipOne",
        },
      });
    });
  });

  describe("when cardinality many", () => {
    it("returns null is there is no relationship", () => {
      // GIVEN
      const relationshipData: RelationshipManyType = { edges: [] };

      // WHEN
      const defaultValue = getRelationshipDefaultValue({ relationshipData });

      // THEN
      expect(defaultValue).to.deep.equal({ source: { type: "user" }, value: [] });
    });

    it("returns user defined relationship", () => {
      // GIVEN
      const relationshipData: RelationshipManyType = {
        edges: [buildRelationshipOneData({ properties: { source: null } })],
      };

      // WHEN
      const defaultValue = getRelationshipDefaultValue({ relationshipData });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: { type: "user" },
        value: [
          {
            id: "relationship-one-id",
          },
        ],
      });
    });
  });
});
