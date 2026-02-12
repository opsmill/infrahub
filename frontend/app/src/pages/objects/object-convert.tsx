import { Navigate, useParams } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import ErrorScreen from "@/shared/components/errors/error-screen";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { ObjectConvert } from "@/entities/nodes/convert/ui/object-convert";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

function ObjectConvertPage() {
  const { objectKind, objectId } = useParams();
  const { isAuthenticated } = useAuth();
  const { schema } = useSchema(objectKind);

  if (!isAuthenticated) {
    return <ErrorScreen message="Please log in to access this page." />;
  }

  if (!schema) {
    return <ErrorScreen message={`Schema ${objectKind} not found.`} />;
  }

  if (!objectId) {
    return <Navigate to={constructPath(`/objects/${objectKind}`)} replace />;
  }

  return (
    <RequireObjectPermissions objectKind={schema.kind ?? ""} loadingClassName="h-[calc(100vh-10.5rem)]">
      {({ permission }) => {
        return <ObjectConvert objectSchema={schema} objectId={objectId} permission={permission} />;
      }}
    </RequireObjectPermissions>
  );
}

export const Component = ObjectConvertPage;
