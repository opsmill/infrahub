import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { useDefaultBranch } from "@/entities/branches/ui/hooks/use-default-branch";
import {
  EDIT_DEFAULT_BRANCH,
  MANAGE_REPOSITORIES,
} from "@/entities/permission/domain/model/permission";
import { getObjectPermissionsQueryOptions } from "@/entities/permission/ui/queries/get-object-permissions.query";
import { useHasGlobalPermission } from "@/entities/permission/ui/queries/has-global-permission.query";
import { REPOSITORY_KIND } from "@/entities/repository/domain/model/repository";

interface PendingPushPermissions {
  canActOnPendingPushes: boolean;
  canReimportOnDefaultBranch: boolean;
}

// These actions run on the default branch whatever branch the user selected, so the backend checks the rights held there.
export function usePendingPushPermissions(): PendingPushPermissions {
  const auth = useAuth();
  const defaultBranch = useDefaultBranch();
  const { data: permission } = useQuery({
    ...getObjectPermissionsQueryOptions({
      kind: REPOSITORY_KIND,
      branchName: defaultBranch?.name ?? "",
      userId: auth.user?.id,
    }),
    enabled: !!defaultBranch,
  });
  const { data: canManageRepositories = false } = useHasGlobalPermission(MANAGE_REPOSITORIES);
  const { data: canEditDefaultBranch = false } = useHasGlobalPermission(EDIT_DEFAULT_BRANCH);
  const canUpdate = permission?.update.isAllowed ?? false;

  return {
    canActOnPendingPushes: canUpdate && canManageRepositories && canEditDefaultBranch,
    canReimportOnDefaultBranch: canUpdate && canEditDefaultBranch,
  };
}
