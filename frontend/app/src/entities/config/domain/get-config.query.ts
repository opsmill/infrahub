import { getConfig } from "@/entities/config/domain/get-config";
import { queryOptions, useQuery } from "@tanstack/react-query";

export const getConfigQueryOptions = () => {
  return queryOptions({
    queryKey: ["config"],
    queryFn: getConfig,
  });
};

export const useGetConfig = () => {
  return useQuery(getConfigQueryOptions());
};
