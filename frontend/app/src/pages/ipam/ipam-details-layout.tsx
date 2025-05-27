import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { ObjectDetailsMenu } from "@/entities/nodes/object/ui/object-details/object-details-menu";
import { ObjectDetailsTab } from "@/entities/nodes/object/ui/object-details/object-details-tab";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { getRelationshipsVisibleInTab } from "@/entities/nodes/object/utils/get-relationships-visible-in-tab";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { Permission } from "@/entities/permission/types";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";
import { ModelSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { LinkTab } from "@/shared/components/ui/link";
import { IdCardIcon } from "lucide-react";
import { Outlet, useParams } from "react-router";

interface IpamDetailsPageProps {
  objectSchema: ModelSchema;
  objectId: string;
  permission: Permission;
}

function IpamDetailsLayout({ objectSchema, objectId, permission }: IpamDetailsPageProps) {
  const { isPending, error, data } = useGetObject({ objectSchema, objectId });

  if (isPending) {
    return <LoadingIndicator className="h-full" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  return (
    <Col className="gap-0 overflow-hidden">
      <Row className="p-2">
        <h2 className="font-semibold text-lg justify-between">{getNodeLabel(data)}</h2>

        <ObjectDetailsMenu objectSchema={objectSchema} objectData={data} permission={permission} />
      </Row>
      <Row className="border-b border-gray-200">
        <LinkTab href={getObjectDetailsUrl(objectSchema.kind as string, objectId)}>
          <IdCardIcon className="size-4" />
          Details
        </LinkTab>

        {getRelationshipsVisibleInTab(objectSchema.relationships ?? []).map((relationship) => {
          return (
            <ObjectDetailsTab
              key={relationship.name}
              parentKind={objectSchema.kind as string}
              parentId={objectId}
              relationship={relationship}
            />
          );
        })}
      </Row>

      <Outlet />
    </Col>
  );
}

export const Component = () => {
  const { objectKind, objectId } = useParams() as { objectKind: string; objectId: string };
  const { schema } = useSchema(objectKind);

  if (!schema) {
    return <ErrorScreen message={`Schema for ${objectKind} not found.`} />;
  }

  return (
    <RequireObjectPermissions objectKind={objectKind}>
      {({ permission }) => {
        return (
          <IpamDetailsLayout objectSchema={schema} objectId={objectId} permission={permission} />
        );
      }}
    </RequireObjectPermissions>
  );
};
