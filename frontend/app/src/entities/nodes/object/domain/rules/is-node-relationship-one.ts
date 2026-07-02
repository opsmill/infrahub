import type { NodeFields, NodeRelationshipOne } from "@/entities/nodes/object/domain/model/node";

export const isNodeRelationshipOne = (value: NodeFields[string]): value is NodeRelationshipOne => {
  return value !== null && typeof value === "object" && "node" in value && !("edges" in value);
};
