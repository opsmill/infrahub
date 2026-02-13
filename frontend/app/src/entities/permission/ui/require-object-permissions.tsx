import ErrorScreen from "@/shared/components/errors/error-screen";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { useGetObjectPermissions } from "@/entities/permission/domain/get-object-permissions.query";
import type { Permission } from "@/entities/permission/types";

export interface RequireObjectPermissionsProps {
  objectKind: string;
  loadingClassName?: string;
  children?: React.ReactNode | ((params: { permission: Permission }) => React.ReactNode);
}

export function RequireObjectPermissions({
  objectKind,
  children,
  loadingClassName,
}: RequireObjectPermissionsProps) {
  const { isPending, error, data: permission } = useGetObjectPermissions(objectKind);

  if (isPending) {
    return <LoadingIndicator className={loadingClassName} />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  if (!permission.view.isAllowed) {
    return <UnauthorizedScreen message={permission.view.message} />;
  }

  return typeof children === "function" ? children({ permission }) : children;
}
