import { getConfig } from "@/entities/config/get-config";
import { queryOptions, useSuspenseQuery } from "@tanstack/react-query";

export const getConfigQueryOptions = () => {
  return queryOptions({
    queryKey: ["config"],
    queryFn: getConfig,
  });
};

export const useConfig = () => {
  return useSuspenseQuery(getConfigQueryOptions());
};
