import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { TREE_MAP_CHILD_LIMIT } from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix-tree-map";
import {
  type GetIpPrefixTreeMapParams,
  getIpPrefixTreeMap,
} from "@/entities/ipam/ip-prefixes/domain/use-cases/get-ip-prefix-tree-map";
import { ipPrefixesQueryKeys } from "@/entities/ipam/ip-prefixes/ui/queries/ip-prefix.query-keys";

export function getIpPrefixTreeMapQueryOptions(params: GetIpPrefixTreeMapParams) {
  return queryOptions({
    queryKey: ipPrefixesQueryKeys.treeMap(params),
    queryFn: () => getIpPrefixTreeMap(params),
  });
}

export function useGetIpPrefixTreeMap({ parentId }: { parentId: string }) {
  const { currentBranch } = useCurrentBranch();
  const atDate = useAtomValue(datetimeAtom);

  return useQuery(
    getIpPrefixTreeMapQueryOptions({
      parentId,
      limit: TREE_MAP_CHILD_LIMIT,
      branchName: currentBranch.name,
      atDate,
    })
  );
}
