import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";

import { type GetNodeMetadataParams, getNodeMetadata } from "./get-node-metadata";
import { objectQueryKeys } from "./object.query-keys";

export function getNodeMetadataQueryOptions(params: GetNodeMetadataParams) {
  return queryOptions({
    queryKey: objectQueryKeys.metadata(params),
    queryFn: async () => {
      return getNodeMetadata(params);
    },
  });
}

export function useGetNodeMetadata(params: Omit<GetNodeMetadataParams, keyof ContextParams>) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getNodeMetadataQueryOptions({
      branchName: currentBranch.name,
      atDate: timeMachineDate,
      ...params,
    })
  );
}
