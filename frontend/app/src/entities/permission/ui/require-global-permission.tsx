import type React from "react";

import ErrorScreen from "@/shared/components/errors/error-screen";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { useGlobalPermission } from "@/entities/permission/ui/queries/use-global-permission";

export interface RequireGlobalPermissionProps {
  /** The GLOBAL permission action to require, e.g. `MANAGE_GLOBAL_PREFERENCES`. */
  action: string;
  loadingClassName?: string;
  unauthorizedMessage?: string;
  children?: React.ReactNode;
}

/**
 * Gates its children on a GLOBAL permission — the account-wide counterpart of
 * {@link RequireObjectPermissions}. Renders a loader while resolving, an error screen on failure,
 * and an unauthorized screen when the caller lacks the `action` (super admins pass, via
 * `hasGlobalPermission`).
 */
export function RequireGlobalPermission({
  action,
  children,
  loadingClassName,
  unauthorizedMessage = "You don't have permission to perform this action",
}: RequireGlobalPermissionProps) {
  const { isPending, error, data: isAllowed } = useGlobalPermission(action);

  if (isPending) {
    return <LoadingIndicator className={loadingClassName} />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  if (!isAllowed) {
    return <UnauthorizedScreen message={unauthorizedMessage} />;
  }

  return children;
}
