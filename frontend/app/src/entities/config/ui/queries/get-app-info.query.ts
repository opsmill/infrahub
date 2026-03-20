import { queryOptions, useQuery } from "@tanstack/react-query";

import { getAppInfo } from "@/entities/config/domain/get-app-info";

export const APP_INFO_QUERY_KEY = ["app-info"] as const;

export const getAppInfoQueryOptions = () => {
  return queryOptions({
    queryKey: APP_INFO_QUERY_KEY,
    queryFn: getAppInfo,
    staleTime: 5 * 60 * 1000,
  });
};

export const useGetAppInfo = () => {
  return useQuery(getAppInfoQueryOptions());
};
