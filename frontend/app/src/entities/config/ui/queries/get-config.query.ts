import { queryOptions, useQuery } from "@tanstack/react-query";

import { getConfig } from "@/entities/config/domain/get-config";

export const getConfigQueryOptions = () => {
  return queryOptions({
    queryKey: ["config"],
    queryFn: getConfig,
  });
};

export const useGetConfig = () => {
  return useQuery(getConfigQueryOptions());
};
