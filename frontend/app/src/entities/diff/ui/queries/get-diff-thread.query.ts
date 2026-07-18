import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import { type GetDiffThreadParams, getDiffThread } from "@/entities/diff/domain/get-diff-thread";
import { diffThreadKeys } from "@/entities/diff/ui/queries/diff.query-keys";

export function getDiffThreadQueryOptions(params: GetDiffThreadParams) {
  return queryOptions({
    queryKey: diffThreadKeys.detail(params),
    queryFn: () => getDiffThread(params),
  });
}

export function useGetDiffThread(
  params: GetDiffThreadParams,
  config?: QueryConfig<typeof getDiffThreadQueryOptions>
) {
  return useQuery({ ...getDiffThreadQueryOptions(params), ...config });
}
