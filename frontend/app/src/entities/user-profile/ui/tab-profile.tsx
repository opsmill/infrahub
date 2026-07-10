import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { DetailsColumns } from "@/shared/components/layout/details-columns";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
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

  if (isObjectPending || isPermissionPending) {
    return <LoadingIndicator className="h-[244px]" />;
  }

  if (objectError || permissionError) {
    return <ErrorScreen message={objectError?.message || permissionError?.message} />;
  }

  // The Profile tab owns its layout rather than rendering the generic <ObjectDetails/>: user
  // preferences are a distinct concern, not part of the account node, so the card sits beside the
  // account details in the main column via the shared DetailsColumns primitive.
  return (
    <DetailsColumns>
      <DetailsColumns.Main>
        <ObjectDetailsCard objectSchema={schema} objectData={objectData} permission={permission} />
        <UserPreferencesCard />
      </DetailsColumns.Main>

      <DetailsColumns.Aside>
        <ObjectProfilesGroupsCard
          objectSchema={schema}
          objectData={objectData}
          permission={permission}
        />
        <ObjectActivitiesCard objectKind={objectData.__typename} objectId={objectData.id} />
      </DetailsColumns.Aside>
    </DetailsColumns>
  );
}
