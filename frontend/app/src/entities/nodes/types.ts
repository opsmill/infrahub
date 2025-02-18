// https://docs.infrahub.app/reference/schema/relationship/#kind
export type RelationshipKind =
  | "Generic"
  | "Attribute"
  | "Component"
  | "Parent"
  | "Group"
  | "Hierarchy"
  | "Profile";

export type NodeCore = {
  id: string;
  hfid?: string[] | null;
  display_label?: string | null;
  __typename: string;
};

export type NodeAttribute = {
  id: string;
  value: string | number | boolean | null;
};

export type NodeRelationshipOne = {
  node: NodeCore;
};

export type NodeRelationshipMany = {
  edges: Array<NodeRelationshipOne>;
};

export type NodeRelationship = NodeRelationshipOne | NodeRelationshipMany;

export type NodeObject = NodeCore & {
  [key: string]: NodeAttribute | NodeRelationship;
};
