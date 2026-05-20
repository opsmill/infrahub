import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import {
  type GetFileContentDiffParams,
  getFileContentDiff,
} from "@/entities/diff/domain/get-file-content-diff";
import { fileContentDiffKeys } from "@/entities/diff/ui/queries/diff.query-keys";

export function getFileContentDiffQueryOptions(params: GetFileContentDiffParams) {
  return queryOptions({
    queryKey: fileContentDiffKeys.detail(params),
    queryFn: () => getFileContentDiff(params),
  });
}

export function useGetFileContentDiff(
  params: GetFileContentDiffParams,
  config?: QueryConfig<typeof getFileContentDiffQueryOptions>
) {
  return useQuery({ ...getFileContentDiffQueryOptions(params), ...config });
}
