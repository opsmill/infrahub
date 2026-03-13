import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import {
  type GetArtifactFileParams,
  getArtifactFile,
} from "@/entities/artifacts/domain/get-artifact-file";
import { artifactsQueryKeys } from "@/entities/artifacts/ui/queries/artifacts.query-keys";

export function getArtifactFileQueryOptions({ storageId, contentType }: GetArtifactFileParams) {
  return queryOptions({
    queryKey: artifactsQueryKeys.file(storageId, contentType),
    queryFn: () => getArtifactFile({ storageId, contentType }),
  });
}

export function useGetArtifactFile(
  params: GetArtifactFileParams,
  config?: QueryConfig<typeof getArtifactFileQueryOptions>
) {
  return useQuery({ ...getArtifactFileQueryOptions(params), ...config });
}
