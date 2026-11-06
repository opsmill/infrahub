import type { ContextParams } from "@/shared/api/types";

import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";

export interface IpPrefixTreeMapKeysParams extends ContextParams {
  parentId: string;
  limit: number;
}

// Rooted under the shared object keys so every existing object mutation invalidation reaches the map.
export const ipPrefixesQueryKeys = {
  treeMap: (params: IpPrefixTreeMapKeysParams) =>
    [...objectQueryKeys.allWithContext(params), "ip-prefix-tree-map", params] as const,
} as const;
