import { queryOptions, useQuery } from "@tanstack/react-query";

import { hasGlobalPermission } from "@/entities/permission/domain/use-cases/has-global-permission";

export function globalPermissionQueryOptions(action: string) {
  return queryOptions({
    queryKey: ["permissions", "global", action],
    queryFn: () => hasGlobalPermission(action),
  });
}

export function useGlobalPermission(action: string) {
  return useQuery(globalPermissionQueryOptions(action));
}
