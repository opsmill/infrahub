import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import { type GetDiffSummaryParams, getDiffSummary } from "@/entities/diff/domain/get-diff-summary";
import { diffSummaryKeys } from "@/entities/diff/ui/queries/diff.query-keys";

export function getDiffSummaryQueryOptions({
  branch,
  filters,
  proposedChangeId,
}: GetDiffSummaryParams) {
  return queryOptions({
    queryKey: diffSummaryKeys.detail({ branch, filters, proposedChangeId }),
    queryFn: () => getDiffSummary({ branch, filters, proposedChangeId }),
  });
}

export type UseGetDiffSummaryConfig = QueryConfig<typeof getDiffSummaryQueryOptions>;

export function useGetDiffSummary(params: GetDiffSummaryParams, config?: UseGetDiffSummaryConfig) {
  return useQuery({ ...getDiffSummaryQueryOptions(params), ...config });
}
