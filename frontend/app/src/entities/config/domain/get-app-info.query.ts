import { queryOptions, useQuery } from "@tanstack/react-query";

import { getAppInfo } from "@/entities/config/domain/get-app-info";

export const getAppInfoQueryOptions = () => {
  return queryOptions({
    queryKey: ["app-info"],
    queryFn: getAppInfo,
  });
};

export const useGetAppInfo = () => {
  return useQuery(getAppInfoQueryOptions());
};
