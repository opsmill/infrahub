import type { AttributeSchema } from "@/entities/schema/domain/model/schema";

// A unique attribute holds each number once across every node, so the pool has a single sequence.
export function canNumberPoolHaveAllocationScope(attribute: AttributeSchema): boolean {
  return !attribute.unique;
}
