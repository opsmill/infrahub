import type { NumberPoolForEditingNode } from "@/entities/resource-manager/api/get-number-pool-for-editing-from-api";
import type { NumberPoolForEditing } from "@/entities/resource-manager/domain/model/number-pool";
import type { StoredRange } from "@/entities/resource-manager/domain/model/number-pool-range";

type RangeNode = NonNullable<NumberPoolForEditingNode["ranges"]["edges"][number]["node"]>;

function toStoredRange(range: RangeNode): StoredRange {
  const weight = range.allocation_weight?.value;

  return {
    id: range.id,
    start: BigInt(String(range.start?.value)),
    end: BigInt(String(range.end?.value)),
    weight: weight === null || weight === undefined ? null : Number(weight),
  };
}

// A scope element is read as a plain name or as an object with a name, because the server can return either shape.
function toScopeElementName(element: unknown): string[] {
  if (typeof element === "string") return [element];
  if (typeof element === "object" && element !== null && "name" in element) {
    return typeof element.name === "string" ? [element.name] : [];
  }
  return [];
}

export function toNumberPoolForEditing(node: NumberPoolForEditingNode): NumberPoolForEditing {
  const scope = node.allocation_scope?.value;

  return {
    id: node.id,
    name: node.name?.value ?? "",
    description: node.description?.value ?? "",
    node: node.node?.value ?? "",
    nodeAttribute: node.node_attribute?.value ?? "",
    allocationScope: Array.isArray(scope) ? scope.flatMap(toScopeElementName) : [],
    poolType: node.pool_type?.value === "Schema" ? "Schema" : "User",
    ranges: node.ranges.edges.flatMap(({ node: range }) => (range ? [toStoredRange(range)] : [])),
  };
}
