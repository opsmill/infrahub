import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { hasGlobalPermission } from "@/entities/permission/domain/use-cases/has-global-permission";
import { globalPermissionQueryKeys } from "@/entities/permission/ui/queries/permissions-query.keys";

export const hasGlobalPermissionQueryOptions = (action: string, userId?: string) =>
  queryOptions({
    queryKey: globalPermissionQueryKeys.byAction(userId, action),
    queryFn: () => hasGlobalPermission(action),
  });

export function useHasGlobalPermission(
  action: string,
  config?: QueryConfig<typeof hasGlobalPermissionQueryOptions>
) {
  const auth = useAuth();

  return useQuery({ ...hasGlobalPermissionQueryOptions(action, auth.user?.id), ...config });
}
