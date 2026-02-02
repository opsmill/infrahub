import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import { artifactsDiffKeys } from "@/entities/diff/domain/diff.query-keys";
import {
  type GetArtifactsDiffParams,
  getArtifactsDiff,
} from "@/entities/diff/domain/get-artifacts-diff";

export function getArtifactsDiffQueryOptions({ branch }: GetArtifactsDiffParams) {
  return queryOptions({
    queryKey: artifactsDiffKeys.list(branch),
    queryFn: () => getArtifactsDiff({ branch }),
  });
}

export function useGetArtifactsDiff(
  params: GetArtifactsDiffParams,
  config?: QueryConfig<typeof getArtifactsDiffQueryOptions>
) {
  return useQuery({ ...getArtifactsDiffQueryOptions(params), ...config });
}
