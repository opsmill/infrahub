import { queryOptions } from "@tanstack/react-query";

import { refreshAccessToken } from "@/entities/authentication/domain/refresh-access-token";

export function refreshAccessTokenQueryOptions() {
  return queryOptions({
    queryKey: ["refresh-access-token"],
    queryFn: refreshAccessToken,
    staleTime: 0,
    gcTime: 0,
    retry: false,
  });
}
