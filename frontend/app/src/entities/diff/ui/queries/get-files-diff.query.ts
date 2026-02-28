import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import { filesDiffKeys } from "@/entities/diff/ui/queries/diff.query-keys";
import { type GetFilesDiffParams, getFilesDiff } from "@/entities/diff/domain/get-files-diff";

export function getFilesDiffQueryOptions({ branchName }: GetFilesDiffParams) {
  return queryOptions({
    queryKey: filesDiffKeys.list(branchName),
    queryFn: () => getFilesDiff({ branchName }),
  });
}

export function useGetFilesDiff(
  params: GetFilesDiffParams,
  config?: QueryConfig<typeof getFilesDiffQueryOptions>
) {
  return useQuery({ ...getFilesDiffQueryOptions(params), ...config });
}
