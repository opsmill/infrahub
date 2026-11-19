export type AttributeKind = "Text" | "Number" | "Boolean" | "Dropdown";

export interface SchemaAttribute {
  name: string;
  label: string;
  kind: AttributeKind;
  choices?: string[];
}

export interface SchemaRelationship {
  name: string;
  label: string;
  peer: string;
  cardinality: "one" | "many";
}

export interface SchemaKind {
  kind: string;
  label: string;
  displayAttribute: string;
  attributes: SchemaAttribute[];
  relationships: SchemaRelationship[];
}

export type AttributeValue = string | number | boolean | null;

export interface GraphNode {
  id: string;
  kind: string;
  attributes: Record<string, AttributeValue>;
  relationships: Record<string, string | string[] | null>;
}

export type NodeStore = Record<string, GraphNode>;

export interface AttributeUpdate {
  nodeId: string;
  attribute: string;
  value: AttributeValue;
}

export type Schema = Record<string, SchemaKind>;
