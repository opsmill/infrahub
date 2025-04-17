import { useGetObjectPermissions } from "@/entities/permission/domain/get-object-permissions.query";
import ErrorScreen from "@/shared/components/errors/error-screen";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Permission } from "@/entities/permission/types";

export interface RequireObjectPermissionsProps {
  objectKind: string;
  children?: React.ReactNode | ((params: { permission: Permission }) => React.ReactNode);
}

export function RequireObjectPermissions({ objectKind, children }: RequireObjectPermissionsProps) {
  const { isPending, error, data: permission } = useGetObjectPermissions(objectKind);

  if (isPending) {
    return <LoadingIndicator className="h-[calc(100vh-10.5rem)]" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  if (!permission.view.isAllowed) {
    return <UnauthorizedScreen message={permission.view.message} />;
  }

  return typeof children === "function" ? children({ permission }) : children;
}
