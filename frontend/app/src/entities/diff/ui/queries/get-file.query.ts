import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import { type GetFileParams, getFile } from "@/entities/diff/domain/get-file";
import { fileKeys } from "@/entities/diff/ui/queries/diff.query-keys";

export function getFileQueryOptions(params: GetFileParams) {
  return queryOptions({
    queryKey: fileKeys.detail(params),
    queryFn: () => getFile(params),
  });
}

export function useGetFile(
  params: GetFileParams,
  config?: QueryConfig<typeof getFileQueryOptions>
) {
  return useQuery({ ...getFileQueryOptions(params), ...config });
}
