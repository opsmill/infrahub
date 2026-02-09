import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { QueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetObjectFileParams,
  getObjectFile,
} from "@/entities/object-file/domain/get-object-file";
import { objectFileQueryKeys } from "@/entities/object-file/domain/object-file.query-keys";

export function getObjectFileQueryOptions({
  nodeId,
  contentType,
  branchName,
  atDate,
}: GetObjectFileParams) {
  return queryOptions({
    queryKey: objectFileQueryKeys.file(nodeId, branchName, atDate, contentType),
    queryFn: () => getObjectFile({ nodeId, contentType, branchName, atDate }),
    enabled: !!nodeId,
  });
}

export function useGetObjectFile(
  params: { nodeId: string; contentType?: string },
  config?: QueryConfig<typeof getObjectFileQueryOptions>
) {
  const { currentBranch } = useCurrentBranch();
  const atDate = useAtomValue(datetimeAtom);

  return useQuery({
    ...getObjectFileQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate,
    }),
    ...config,
  });
}
