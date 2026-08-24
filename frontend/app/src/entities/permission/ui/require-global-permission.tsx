import type React from "react";

import ErrorScreen from "@/shared/components/errors/error-screen";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { useHasGlobalPermission } from "@/entities/permission/ui/queries/has-global-permission.query";

export interface RequireGlobalPermissionProps {
  action: string;
  loadingClassName?: string;
  unauthorizedMessage?: string;
  children?: React.ReactNode;
}

export function RequireGlobalPermission({
  action,
  children,
  loadingClassName,
  unauthorizedMessage = "You don't have permission to perform this action",
}: RequireGlobalPermissionProps) {
  const { isPending, error, data: isAllowed } = useHasGlobalPermission(action);

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
