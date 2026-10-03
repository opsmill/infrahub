import type { TreeMapData } from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix-tree-map";
import { parsePrefixLength } from "@/entities/ipam/ip-prefixes/domain/rules/parse-prefix-length";
import type { NodeObject } from "@/entities/nodes/object/domain/model/node";

export type TreeMapParent = TreeMapData["parent"] & { kind: string };

function readAttributeValue(node: NodeObject, name: string): unknown {
  const field = node[name];
  if (field === null || field === undefined || typeof field !== "object") return undefined;
  return "value" in field ? field.value : undefined;
}

/**
 * Projects a loaded IP prefix node onto the parent shape the tree map needs, or returns `null`
 * when the node has no parseable `prefix` attribute.
 */
export function getTreeMapParent(node: NodeObject, kind: string): TreeMapParent | null {
  const cidr = readAttributeValue(node, "prefix");
  if (typeof cidr !== "string") return null;

  let size: TreeMapData["parent"]["size"];
  try {
    size = parsePrefixLength(cidr);
  } catch {
    return null;
  }

  const memberType = readAttributeValue(node, "member_type");
  const utilization = readAttributeValue(node, "utilization");

  return {
    id: node.id,
    kind,
    cidr,
    size,
    memberType: memberType === "address" ? "address" : "prefix",
    utilization: typeof utilization === "number" ? utilization : null,
  };
}
