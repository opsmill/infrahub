import { useParams } from "react-router";

import { Col } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { IP_SUMMARY_RELATIONSHIPS_BLACKLIST } from "@/entities/ipam/constants";
import { ObjectActivitiesCard } from "@/entities/nodes/object/ui/object-details/object-activities-card";
import { ObjectDetailsCard } from "@/entities/nodes/object/ui/object-details/object-details-card";
import { ObjectProfilesGroupsCard } from "@/entities/nodes/object/ui/object-details/object-profiles-groups-card";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import type { Permission } from "@/entities/permission/types";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";
import type { ModelSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface IpamDetailsContentProps {
  objectSchema: ModelSchema;
  objectId: string;
  permission: Permission;
}

function IpamDetailsContent({ objectSchema, objectId, permission }: IpamDetailsContentProps) {
  const { isPending, error, data } = useGetObject({ objectSchema, objectId });

  if (isPending) {
    return <LoadingIndicator className="h-full" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  return (
    <div className="flex flex-col gap-2 overflow-auto p-2 xl:grid xl:grid-cols-3 xl:items-start">
      <Col className="shrink-0 grow md:col-span-2">
        <ObjectDetailsCard
          objectSchema={objectSchema}
          objectData={data}
          permission={permission}
          excludeRelationships={IP_SUMMARY_RELATIONSHIPS_BLACKLIST}
        />
      </Col>

      <Col>
        <ObjectProfilesGroupsCard
          objectSchema={objectSchema}
          objectData={data}
          permission={permission}
        />
        <ObjectActivitiesCard objectKind={data.__typename} objectId={data.id} />
      </Col>
    </div>
  );
}

export const Component = () => {
  const { objectKind, objectId } = useParams() as { objectKind: string; objectId: string };
  const { schema } = useSchema(objectKind);

  if (!schema) {
    return <ErrorScreen message={`Schema for ${objectKind} not found.`} />;
  }

  return (
    <RequireObjectPermissions objectKind={schema.kind!}>
      {({ permission }) => (
        <IpamDetailsContent objectSchema={schema} objectId={objectId} permission={permission} />
      )}
    </RequireObjectPermissions>
  );
};
