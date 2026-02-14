import type { components } from "@/shared/api/rest/types.generated";

// https://docs.infrahub.app/reference/schema/relationship/#kind
export type RelationshipKind = components["schemas"]["RelationshipKind"];

export interface NodeCore {
  id: string;
  hfid?: string[] | null;
  display_label?: string | null;
  __typename: string;
}

export interface NodeAttribute<T = string | number | boolean | string[] | null> {
  value: T;
}

export interface NodeAttributeMetadata {
  updated_at: string;
  is_default: boolean;
  is_from_profile: boolean;
  is_protected: boolean;
  is_visible: boolean;
  source: NodeCore | null;
  owner: NodeCore | null;
}

export interface NodeAttributeWithMetadata extends NodeAttribute, NodeAttributeMetadata {}

export interface NodeRelationshipOne {
  node: NodeCore | null;
}

export interface NodeRelationshipMany {
  edges: Array<NodeRelationshipOne>;
}

export type NodeRelationship = NodeRelationshipOne | NodeRelationshipMany;

export interface NodeRelationshipMetadata {
  is_protected: boolean | null;
  updated_at: string | null;
  source: NodeCore | null;
  owner: NodeCore | null;
}

export interface NodeRelationshipOneWithMetadata extends NodeRelationshipOne {
  properties: NodeRelationshipMetadata;
}

export interface NodeRelationshipManyWithMetadata extends NodeRelationshipMany {
  edges: Array<NodeRelationshipOneWithMetadata>;
}

export type NodeRelationshipWithMetadata =
  | NodeRelationshipOneWithMetadata
  | NodeRelationshipManyWithMetadata;

// Include NodeCore's value types so that `NodeCore & NodeFields` doesn't create
// an impossible intersection (e.g. `id` must be both `string` and `NodeAttribute`).
type NodeCorePropertyValue = NodeCore[keyof NodeCore];

export type NodeFields = Record<string, NodeAttribute | NodeRelationship | NodeCorePropertyValue>;
export type NodeFieldsWithMetadata = Record<
  string,
  NodeAttributeWithMetadata | NodeRelationshipWithMetadata | NodeCorePropertyValue
>;

export type NodeObject = NodeCore & NodeFields;
export type NodeObjectWithMetadata = NodeCore & NodeFieldsWithMetadata;

export type NodeFileObject = NodeObject & {
  file_name: NodeAttribute<string>;
  file_size: NodeAttribute<number>;
  file_type: NodeAttribute<string>;
  storage_id: NodeAttribute<string>;
  checksum: NodeAttribute<string>;
};

export interface NodeMetadata {
  created_at: string | null;
  created_by: NodeCore | null;
  updated_at: string | null;
  updated_by: NodeCore | null;
}

export interface NodeCoreWithChildrenCount extends NodeCore {
  children: {
    count: number;
  };
}

export interface NodeCoreWithParent extends NodeCore {
  parent: NodeRelationshipOne;
}
