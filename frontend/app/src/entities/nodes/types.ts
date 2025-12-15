import type { components } from "@/shared/api/rest/types.generated";

// https://docs.infrahub.app/reference/schema/relationship/#kind
export type RelationshipKind = components["schemas"]["RelationshipKind"];

export interface NodeCore {
  id: string;
  hfid?: string[] | null;
  display_label?: string | null;
  __typename: string;
}

export interface NodeAttribute {
  id: string;
  value: string | number | boolean | string[] | null;
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
  is_protected: boolean;
  updated_at: string;
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

export type NodeObject = NodeCore & {
  [key: string]: NodeAttribute | NodeRelationship;
};

export type NodeObjectWithMetadata = NodeCore & {
  [key: string]: NodeAttributeWithMetadata | NodeRelationshipWithMetadata;
};

export interface NodeCoreWithChildrenCount extends NodeCore {
  children: {
    count: number;
  };
}

export interface NodeCoreWithParent extends NodeCore {
  parent: NodeRelationshipOne;
}
