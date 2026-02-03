import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import { getFileContentFromApi } from "../api/get-file-content-from-api";
import { fileContentQueryKeys } from "./file-content.query-keys";

export interface GetFileContentParams {
  url: string;
}

export function getFileContentQueryOptions({ url }: GetFileContentParams) {
  return queryOptions({
    queryKey: fileContentQueryKeys.byUrl(url),
    queryFn: () => getFileContentFromApi({ url }),
    enabled: !!url,
  });
}

export function useGetFileContent(
  params: GetFileContentParams,
  config?: QueryConfig<typeof getFileContentQueryOptions>
) {
  return useQuery({
    ...getFileContentQueryOptions(params),
    ...config,
  });
}
