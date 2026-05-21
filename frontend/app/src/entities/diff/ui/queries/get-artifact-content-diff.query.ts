import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import {
  type GetArtifactContentDiffParams,
  getArtifactContentDiff,
} from "@/entities/diff/domain/get-artifact-content-diff";
import { artifactContentDiffKeys } from "@/entities/diff/ui/queries/diff.query-keys";

export function getArtifactContentDiffQueryOptions(params: GetArtifactContentDiffParams) {
  return queryOptions({
    queryKey: artifactContentDiffKeys.detail(params),
    queryFn: () => getArtifactContentDiff(params),
  });
}

export function useGetArtifactContentDiff(
  params: GetArtifactContentDiffParams,
  config?: QueryConfig<typeof getArtifactContentDiffQueryOptions>
) {
  return useQuery({ ...getArtifactContentDiffQueryOptions(params), ...config });
}
