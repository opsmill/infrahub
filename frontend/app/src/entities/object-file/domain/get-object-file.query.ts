import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import {
  type GetObjectFileParams,
  getObjectFile,
} from "@/entities/object-file/domain/get-object-file";
import { objectFileQueryKeys } from "@/entities/object-file/domain/object-file.query-keys";

export function getObjectFileQueryOptions({ nodeId }: GetObjectFileParams) {
  return queryOptions({
    queryKey: objectFileQueryKeys.file(nodeId),
    queryFn: () => getObjectFile({ nodeId }),
    enabled: !!nodeId,
  });
}

export function useGetObjectFile(
  params: GetObjectFileParams,
  config?: QueryConfig<typeof getObjectFileQueryOptions>
) {
  return useQuery({ ...getObjectFileQueryOptions(params), ...config });
}
