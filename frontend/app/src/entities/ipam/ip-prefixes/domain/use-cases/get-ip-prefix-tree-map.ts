import type { ResultOf } from "@/shared/api/graphql/client";

import {
  type GET_IP_PREFIX_TREE_MAP,
  type GetIpPrefixTreeMapFromApiParams,
  getIpPrefixTreeMapFromApi,
} from "@/entities/ipam/ip-prefixes/api/get-ip-prefix-tree-map-from-api";
import {
  IP_PREFIX_AVAILABLE_KIND,
  IP_PREFIX_GENERIC,
} from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix";
import type {
  PrefixSize,
  TreeMapChild,
  TreeMapData,
  TreeMapFreeBlock,
} from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix-tree-map";
import { parsePrefixLength } from "@/entities/ipam/ip-prefixes/domain/rules/parse-prefix-length";

export type GetIpPrefixTreeMapParams = GetIpPrefixTreeMapFromApiParams;

// The caller already holds the parent node, so the use-case returns only what the query adds.
export type GetIpPrefixTreeMapResult = Omit<TreeMapData, "parent">;

type TreeMapPage = NonNullable<ResultOf<typeof GET_IP_PREFIX_TREE_MAP>[typeof IP_PREFIX_GENERIC]>;
type TreeMapNode = NonNullable<TreeMapPage["edges"][number]["node"]>;

function parsePrefixSizeOrNull(cidr: string): PrefixSize | null {
  try {
    return parsePrefixLength(cidr);
  } catch {
    return null;
  }
}

function toMemberType(value: unknown): TreeMapChild["memberType"] | null {
  return value === "address" || value === "prefix" ? value : null;
}

function toTreeMapChild(node: TreeMapNode): TreeMapChild | null {
  const cidr = node.prefix?.value;
  if (!cidr || !node.id) return null;

  const size = parsePrefixSizeOrNull(cidr);
  if (!size) return null;

  const memberType = toMemberType(node.member_type?.value);
  if (!memberType) return null;

  const utilizationValue = node.utilization?.value;

  return {
    id: node.id,
    kind: node.__typename,
    cidr,
    size,
    memberType,
    isPool: node.is_pool?.value === true,
    utilization: typeof utilizationValue === "number" ? utilizationValue : null,
    description: node.description?.value ?? null,
    memberCount: memberType === "address" ? node.ip_addresses.count : node.children.count,
  };
}

function toTreeMapFreeBlock(node: TreeMapNode): TreeMapFreeBlock | null {
  const cidr = node.prefix?.value;
  if (!cidr) return null;

  const size = parsePrefixSizeOrNull(cidr);
  if (!size) return null;

  return { cidr, size };
}

export async function getIpPrefixTreeMap(
  params: GetIpPrefixTreeMapParams
): Promise<GetIpPrefixTreeMapResult> {
  const { data, errors } = await getIpPrefixTreeMapFromApi(params);

  if (errors) {
    throw new Error(errors.map((error) => error.message).join("; "));
  }

  const page = data?.[IP_PREFIX_GENERIC];
  if (!page) {
    throw new Error("The IP prefix tree map query returned no prefix data.");
  }

  const nodes = page.edges.flatMap((edge) => (edge.node ? [edge.node] : []));

  const children: TreeMapChild[] = [];
  const freeBlocks: TreeMapFreeBlock[] = [];
  let droppedChildCount = 0;

  for (const node of nodes) {
    if (node.__typename === IP_PREFIX_AVAILABLE_KIND) {
      const freeBlock = toTreeMapFreeBlock(node);
      if (freeBlock) freeBlocks.push(freeBlock);
      continue;
    }

    const child = toTreeMapChild(node);
    if (child) {
      children.push(child);
    } else {
      droppedChildCount += 1;
      console.warn("Skipping an IP prefix the tree map cannot place", node.id, node.prefix?.value);
    }
  }

  // A dropped node cannot be placed anywhere, so it leaves both the count and the cap arithmetic.
  const totalChildCount = Math.max((page.count ?? 0) - droppedChildCount, children.length);

  return {
    children,
    freeBlocks,
    totalChildCount,
    isCapped: totalChildCount > children.length,
  };
}
