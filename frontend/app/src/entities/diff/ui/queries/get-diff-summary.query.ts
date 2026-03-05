import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import { type GetDiffSummaryParams, getDiffSummary } from "@/entities/diff/domain/get-diff-summary";

export function getDiffSummaryQueryOptions({ branch, filters }: GetDiffSummaryParams) {
  return queryOptions({
    queryKey: ["diff-summary", branch, filters],
    queryFn: () => getDiffSummary({ branch, filters }),
  });
}

export type UseGetDiffSummaryConfig = QueryConfig<typeof getDiffSummaryQueryOptions>;

export function useGetDiffSummary(params: GetDiffSummaryParams, config?: UseGetDiffSummaryConfig) {
  return useQuery({ ...getDiffSummaryQueryOptions(params), ...config });
}
