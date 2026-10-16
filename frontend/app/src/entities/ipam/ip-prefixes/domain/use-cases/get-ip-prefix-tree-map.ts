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
  MemberType,
  PrefixSize,
  TreeMapChild,
  TreeMapData,
  TreeMapFreeBlock,
  TreeMapParent,
} from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix-tree-map";
import { buildPrefixSize } from "@/entities/ipam/ip-prefixes/domain/rules/prefix-size";

export type GetIpPrefixTreeMapParams = GetIpPrefixTreeMapFromApiParams;

export type GetIpPrefixTreeMapResult = TreeMapData;

type TreeMapResult = ResultOf<typeof GET_IP_PREFIX_TREE_MAP>;
type TreeMapPage = NonNullable<TreeMapResult[typeof IP_PREFIX_GENERIC]>;
type TreeMapNode = NonNullable<TreeMapPage["edges"][number]["node"]>;
type ParentNode = NonNullable<NonNullable<TreeMapResult["parent"]>["edges"][number]["node"]>;

interface PrefixAttribute {
  value?: string | null;
  prefixlen?: number | null;
  version?: number | null;
}

function toPrefixSize(prefix: PrefixAttribute | null | undefined): PrefixSize | null {
  if (
    !prefix?.value ||
    typeof prefix.prefixlen !== "number" ||
    typeof prefix.version !== "number"
  ) {
    return null;
  }
  try {
    return buildPrefixSize({
      cidr: prefix.value,
      prefixLength: prefix.prefixlen,
      version: prefix.version,
    });
  } catch {
    return null;
  }
}

function toMemberType(value: unknown): MemberType | null {
  return value === "address" || value === "prefix" ? value : null;
}

function toUtilization(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}

function toTreeMapChild(node: TreeMapNode): TreeMapChild | null {
  const size = toPrefixSize(node.prefix);
  const memberType = toMemberType(node.member_type?.value);
  if (!size || !memberType || !node.id || !node.prefix?.value) return null;

  return {
    id: node.id,
    kind: node.__typename,
    cidr: node.prefix.value,
    size,
    memberType,
    isPool: node.is_pool?.value === true,
    utilization: toUtilization(node.utilization?.value),
    description: node.description?.value ?? null,
    memberCount: memberType === "address" ? node.ip_addresses.count : node.children.count,
  };
}

function toTreeMapFreeBlock(node: TreeMapNode): TreeMapFreeBlock | null {
  const size = toPrefixSize(node.prefix);
  if (!size || !node.prefix?.value) return null;
  return { cidr: node.prefix.value, size };
}

function toTreeMapParent(node: ParentNode | undefined): TreeMapParent {
  const size = node ? toPrefixSize(node.prefix) : null;
  const memberType = toMemberType(node?.member_type?.value);
  if (!node?.id || !node.prefix?.value || !size || !memberType) {
    throw new Error("The IP prefix tree map query returned no usable parent prefix.");
  }
  return {
    id: node.id,
    kind: node.__typename,
    cidr: node.prefix.value,
    size,
    memberType,
    utilization: toUtilization(node.utilization?.value),
  };
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

  const parent = toTreeMapParent(data.parent?.edges[0]?.node ?? undefined);
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
    parent,
    children,
    freeBlocks,
    totalChildCount,
    isCapped: totalChildCount > children.length,
  };
}
