import { queryOptions, useQuery } from "@tanstack/react-query";

import { objectFileQueryKeys } from "@/entities/object-file/domain/object-file.query-keys";
import {
  type GetObjectFileParams,
  getObjectFile,
} from "@/entities/object-file/domain/get-object-file";
import type { QueryConfig } from "@/shared/api/types";

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
