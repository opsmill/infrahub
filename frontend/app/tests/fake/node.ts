import type { RelationshipNode } from "../../src/entities/nodes/relationships/domain/types";
import type {
  NodeAttributeWithMetadata,
  NodeRelationshipOneWithMetadata,
} from "../../src/entities/nodes/types";

export const generateNodeAttributeWithMetadata = (
  overrides?: Partial<NodeAttributeWithMetadata>
): NodeAttributeWithMetadata => ({
  value: "test-value",
  updated_at: "2024-01-01T00:00:00Z",
  is_default: false,
  is_from_profile: false,
  is_protected: false,
  is_visible: true,
  source: null,
  owner: null,
  ...overrides,
});

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

export const generateRelationshipNodeWithMetadata = (
  overrides?: Partial<NodeRelationshipOneWithMetadata>
): NodeRelationshipOneWithMetadata => ({
  node: {
    id: "related-node-1",
    display_label: "Related Node",
    __typename: "TestPeer",
  },
  properties: {
    is_protected: false,
    updated_at: "2024-01-01T00:00:00Z",
    source: null,
    owner: null,
  },
  ...overrides,
});
