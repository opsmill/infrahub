import { Navigate, useParams } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import ErrorScreen from "@/shared/components/errors/error-screen";

import { ObjectConvert } from "@/entities/nodes/object/ui/object-convert";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function ObjectConvertPage() {
  const { objectKind, objectid } = useParams<{ objectKind: string; objectid: string }>();
  const { schema } = useSchema(objectKind);

  if (!schema) {
    return <ErrorScreen message={`Schema ${objectKind} not found.`} />;
  }

  if (!objectid) {
    return <Navigate to={constructPath(`/objects/${objectKind}`)} replace />;
  }

  return (
    <RequireObjectPermissions
      objectKind={schema.kind as string}
      loadingClassName="h-[calc(100vh-10.5rem)]"
    >
      {({ permission }) => {
        return <ObjectConvert objectSchema={schema} objectId={objectid} permission={permission} />;
      }}
    </RequireObjectPermissions>
  );
}

export const Component = ObjectConvertPage;
