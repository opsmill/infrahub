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

function toTreeMapChild(node: TreeMapNode): TreeMapChild | null {
  const cidr = node.prefix?.value;
  if (!cidr || !node.id) return null;

  const size = parsePrefixSizeOrNull(cidr);
  if (!size) return null;

  const memberType = node.member_type?.value === "address" ? "address" : "prefix";
  const utilizationValue = node.utilization?.value;

  return {
    id: node.id,
    kind: node.__typename,
    cidr,
    size,
    memberType,
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
  const nodes = page?.edges.flatMap((edge) => (edge.node ? [edge.node] : [])) ?? [];

  const children: TreeMapChild[] = [];
  const freeBlocks: TreeMapFreeBlock[] = [];

  for (const node of nodes) {
    if (node.__typename === IP_PREFIX_AVAILABLE_KIND) {
      const freeBlock = toTreeMapFreeBlock(node);
      if (freeBlock) freeBlocks.push(freeBlock);
    } else {
      const child = toTreeMapChild(node);
      if (child) children.push(child);
    }
  }

  const totalChildCount = page?.count ?? 0;

  return {
    children,
    freeBlocks,
    totalChildCount,
    isCapped: totalChildCount > children.length,
  };
}
