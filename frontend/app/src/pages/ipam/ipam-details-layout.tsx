import { Icon } from "@iconify-icon/react";
import { IdCardIcon } from "lucide-react";
import { Outlet, useParams } from "react-router";

import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { FormContext } from "@/shared/components/form/utils/form-context";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { LinkTab } from "@/shared/components/ui/link";

import { constructPathForIpam } from "@/entities/ipam/ip-namespaces/ui/routing/ipam-urls";
import { IpamDetailsHeader } from "@/entities/ipam/ip-prefixes/ui/ipam-details-header";
import type { NodeObject } from "@/entities/nodes/object/domain/model/node";
import { getRelationshipsVisibleInTab } from "@/entities/nodes/object/domain/rules/get-relationships-visible-in-tab";
import { ObjectDetailsTab } from "@/entities/nodes/object/ui/object-details/object-details-tab";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import type { Permission } from "@/entities/permission/domain/model/permission";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { getSchemaIcon } from "@/entities/schema/domain/rules/get-schema-icon";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export interface IpamDetailsTabsProps {
  objectSchema: ModelSchema;
  objectData: NodeObject;
}

function IpamDetailsTabs({ objectSchema, objectData }: IpamDetailsTabsProps) {
  const relationshipVisible = getRelationshipsVisibleInTab(objectSchema.relationships ?? []);

  return (
    <Row className="border-b">
      <LinkTab to={constructPathForIpam("details")}>
        <IdCardIcon className="size-4" />
        Details
      </LinkTab>

      {relationshipVisible.map((relationship) => {
        return (
          <ObjectDetailsTab
            key={relationship.name}
            parentKind={objectSchema.kind as string}
            parentId={objectData.id}
            relationship={relationship}
          />
        );
      })}
    </Row>
  );
}

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
    <FormContext value={{ parentSchema: objectSchema, parentData: data }}>
      <Col className="gap-0 overflow-hidden pt-2">
        <Row className="gap-1.5 px-2.5 text-custom-blue-800 text-xs">
          <Icon icon={getSchemaIcon(objectSchema)} />
          {objectSchema.label}
        </Row>

        <IpamDetailsHeader
          ipPrefixSchema={objectSchema}
          ipPrefixNode={data}
          permission={permission}
          className="mb-2 px-2.5"
        />

        <IpamDetailsTabs objectSchema={objectSchema} objectData={data} />
        <Outlet />
      </Col>
    </FormContext>
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
      {({ permission }) => {
        return (
          <IpamDetailsLayout objectSchema={schema} objectId={objectId} permission={permission} />
        );
      }}
    </RequireObjectPermissions>
  );
};
