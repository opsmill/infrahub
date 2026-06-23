import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import {
  type GetDiffCommentsParams,
  getDiffComments,
} from "@/entities/diff/domain/get-diff-comments";
import { diffCommentsKeys } from "@/entities/diff/ui/queries/diff.query-keys";

export function getDiffCommentsQueryOptions(params: GetDiffCommentsParams) {
  return queryOptions({
    queryKey: diffCommentsKeys.detail(params),
    queryFn: () => getDiffComments(params),
  });
}

export function useGetDiffComments(
  params: GetDiffCommentsParams,
  config?: QueryConfig<typeof getDiffCommentsQueryOptions>
) {
  return useQuery({ ...getDiffCommentsQueryOptions(params), ...config });
}
