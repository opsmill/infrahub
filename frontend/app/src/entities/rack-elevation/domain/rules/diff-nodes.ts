import type { AttributeValue, NodeStore } from "@/entities/rack-elevation/domain/model/schema";

export interface AttributeChange {
  nodeId: string;
  attribute: string;
  before: AttributeValue;
  after: AttributeValue;
}

export function diffNodes(base: NodeStore, current: NodeStore): AttributeChange[] {
  return Object.values(current).flatMap((node) =>
    Object.entries(node.attributes).flatMap(([attribute, after]) => {
      const before = base[node.id]?.attributes[attribute] ?? null;
      return before === (after ?? null) ? [] : [{ nodeId: node.id, attribute, before, after }];
    })
  );
}
