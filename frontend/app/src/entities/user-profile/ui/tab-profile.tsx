import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ACCOUNT_GENERIC_OBJECT } from "@/shared/config/constants";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { ObjectDetails } from "@/entities/nodes/object/ui/object-details/object-details";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import { useGetObjectPermissions } from "@/entities/permission/ui/queries/get-object-permissions.query";
import type { ModelSchema } from "@/entities/schema/domain/model/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export default function TabProfile() {
  const { schema } = useSchema(ACCOUNT_GENERIC_OBJECT);

  if (!schema) {
    return <NoDataFound message={`Schema ${ACCOUNT_GENERIC_OBJECT} not found`} />;
  }

  return <TabProfileContent schema={schema} />;
}

function TabProfileContent({ schema }: { schema: ModelSchema }) {
  const accountId = useAuth().user?.id;

  const {
    data: objectData,
    error: objectError,
    isPending: isObjectPending,
  } = useGetObject({ objectSchema: schema, objectId: accountId ?? "" }, { enabled: !!accountId });

  const {
    data: permission,
    error: permissionError,
    isPending: isPermissionPending,
  } = useGetObjectPermissions(schema.kind!);

  if (isObjectPending || isPermissionPending) {
    return <LoadingIndicator className="h-[244px]" />;
  }

  if (objectError || permissionError) {
    return <ErrorScreen message={objectError?.message || permissionError?.message} />;
  }

  return <ObjectDetails objectSchema={schema} objectData={objectData} permission={permission} />;
}
