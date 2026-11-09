import { queryOptions, useQuery } from "@tanstack/react-query";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { hasGlobalPermission } from "@/entities/permission/domain/use-cases/has-global-permission";
import { globalPermissionQueryKeys } from "@/entities/permission/ui/queries/permissions-query.keys";

export const hasGlobalPermissionQueryOptions = (action: string, userId?: string) =>
  queryOptions({
    queryKey: globalPermissionQueryKeys.byAction(userId, action),
    queryFn: () => hasGlobalPermission(action),
  });

export function useHasGlobalPermission(action: string) {
  const auth = useAuth();

  return useQuery(hasGlobalPermissionQueryOptions(action, auth.user?.id));
}
