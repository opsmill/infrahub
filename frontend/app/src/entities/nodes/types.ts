// https://docs.infrahub.app/reference/schema/relationship/#kind
export type RelationshipKind =
  | "Generic"
  | "Attribute"
  | "Component"
  | "Parent"
  | "Group"
  | "Hierarchy"
  | "Profile";

export type NodeAttribute = {
  id: string;
  value: string | number | boolean | null;
};

export type NodeRelationshipOne = {
  node: {
    id: string;
    display_label: string;
    __typename: string;
  };
};

export type NodeRelationshipMany = {
  edges: Array<NodeRelationshipOne>;
};

export type NodeRelationship = NodeRelationshipOne | NodeRelationshipMany;

export type NodeObject = {
  id: string;
  hfid?: string;
  display_label?: string;
  __typename: string;
} & {
  [key: string]: NodeAttribute | NodeRelationship;
};
