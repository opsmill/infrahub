import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import { artifactsQueryKeys } from "@/entities/artifacts/domain/artifacts.query-keys";
import {
  type GetArtifactFileParams,
  getArtifactFile,
} from "@/entities/artifacts/domain/get-artifact-file";

export function getArtifactFileQueryOptions({ storageId }: GetArtifactFileParams) {
  return queryOptions({
    queryKey: artifactsQueryKeys.file(storageId),
    queryFn: () => getArtifactFile({ storageId }),
  });
}

export function useGetArtifactFile(
  params: GetArtifactFileParams,
  config?: QueryConfig<typeof getArtifactFileQueryOptions>
) {
  return useQuery({ ...getArtifactFileQueryOptions(params), ...config });
}
