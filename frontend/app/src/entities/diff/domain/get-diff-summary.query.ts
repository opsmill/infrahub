import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import { type GetDiffSummaryParams, getDiffSummary } from "@/entities/diff/domain/get-diff-summary";

export function getDiffSummaryQueryOptions({ branchName }: GetDiffSummaryParams) {
  return queryOptions({
    queryKey: ["diff-summary", branchName],
    queryFn: () => getDiffSummary({ branchName }),
  });
}

export type UseGetDiffSummaryConfig = QueryConfig<typeof getDiffSummaryQueryOptions>;

export function useGetDiffSummary(params: GetDiffSummaryParams, config?: UseGetDiffSummaryConfig) {
  return useQuery({ ...getDiffSummaryQueryOptions(params), ...config });
}
