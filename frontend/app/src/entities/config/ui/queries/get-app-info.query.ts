import { queryOptions, useQuery } from "@tanstack/react-query";

import { getAppInfo } from "@/entities/config/domain/use-cases/get-app-info";

export const APP_INFO_QUERY_KEY = ["app-info"] as const;

// The license state changes with the clock, so a tab left open must pick it up without a reload.
const REFETCH_INTERVAL_MS = 60 * 60 * 1000;

export const getAppInfoQueryOptions = () => {
  return queryOptions({
    queryKey: APP_INFO_QUERY_KEY,
    queryFn: getAppInfo,
    staleTime: 5 * 60 * 1000,
    refetchInterval: REFETCH_INTERVAL_MS,
    refetchOnWindowFocus: "always",
  });
};

export const useGetAppInfo = () => {
  return useQuery(getAppInfoQueryOptions());
};
