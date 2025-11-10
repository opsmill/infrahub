import type { RelationshipNode } from "../../src/entities/nodes/relationships/domain/types";

export const generateRelationshipNode = (
  overrides?: Partial<RelationshipNode>
): RelationshipNode => {
  return {
    id: "test-relationship-id",
    display_label: "Test Relationship",
    __typename: "RelationshipNode",
    ...overrides,
  };
};
