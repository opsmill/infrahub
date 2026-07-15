import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { DetailsLayout } from "@/shared/components/layout/details-layout";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { useTitle } from "@/shared/hooks/useTitle";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import { ObjectActivitiesCard } from "@/entities/nodes/object/ui/object-details/object-activities-card";
import { ObjectDetailsCard } from "@/entities/nodes/object/ui/object-details/object-details-card";
import { ObjectProfilesGroupsCard } from "@/entities/nodes/object/ui/object-details/object-profiles-groups-card";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import { useGetObjectPermissions } from "@/entities/permission/ui/queries/get-object-permissions.query";
import { UserPreferencesCard } from "@/entities/preferences/ui/user-preferences-card";
import { ACCOUNT_GENERIC_OBJECT } from "@/entities/role-manager/domain/model/account";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
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

  useTitle(objectData ? `${getNodeLabel(objectData)} details` : "Profile");

  if (isObjectPending || isPermissionPending) {
    return <LoadingIndicator className="h-[244px]" />;
  }

  if (objectError || permissionError) {
    return <ErrorScreen message={objectError?.message || permissionError?.message} />;
  }

  return (
    <DetailsLayout>
      <DetailsLayout.Main>
        <ObjectDetailsCard objectSchema={schema} objectData={objectData} permission={permission} />
        <UserPreferencesCard />
      </DetailsLayout.Main>

      <DetailsLayout.Aside>
        <ObjectProfilesGroupsCard
          objectSchema={schema}
          objectData={objectData}
          permission={permission}
        />
        <ObjectActivitiesCard objectKind={objectData.__typename} objectId={objectData.id} />
      </DetailsLayout.Aside>
    </DetailsLayout>
  );
}
