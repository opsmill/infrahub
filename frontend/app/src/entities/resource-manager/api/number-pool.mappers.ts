import type { NumberPoolForEditingNode } from "@/entities/resource-manager/api/get-number-pool-for-editing-from-api";
import type {
  NumberPoolForEditing,
  StoredRange,
} from "@/entities/resource-manager/domain/model/number-pool-range";

type RangeNode = NonNullable<NumberPoolForEditingNode["ranges"]["edges"][number]["node"]>;

function toStoredRange(range: RangeNode): StoredRange {
  const weight = range.allocation_weight?.value;

  return {
    id: range.id,
    start: Number(range.start?.value),
    end: Number(range.end?.value),
    weight: weight === null || weight === undefined ? null : Number(weight),
  };
}

export function toNumberPoolForEditing(node: NumberPoolForEditingNode): NumberPoolForEditing {
  const scope = node.allocation_scope?.value;

  return {
    id: node.id,
    name: node.name?.value ?? "",
    description: node.description?.value ?? "",
    node: node.node?.value ?? "",
    nodeAttribute: node.node_attribute?.value ?? "",
    allocationScope: Array.isArray(scope) ? scope : [],
    poolType: node.pool_type?.value === "Schema" ? "Schema" : "User",
    ranges: node.ranges.edges.flatMap(({ node: range }) => (range ? [toStoredRange(range)] : [])),
  };
}
