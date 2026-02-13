import type { NodeFields, NodeRelationshipMany } from "@/entities/nodes/types";

export const isNodeRelationshipMany = (
  value: NodeFields[string]
): value is NodeRelationshipMany => {
  return value !== null && typeof value === "object" && "edges" in value;
};
