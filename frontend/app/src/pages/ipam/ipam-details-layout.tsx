import { Icon } from "@iconify-icon/react";
import { Outlet, useParams } from "react-router";

import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { FormContext } from "@/shared/components/form/utils/form-context";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { IpamDetailsHeader } from "@/entities/ipam/ip-prefixes/ui/ipam-details-header";
import { IpamDetailsTabs } from "@/entities/ipam/ipam-details-tabs";
import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import type { Permission } from "@/entities/permission/types";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";
import type { ModelSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { getSchemaIcon } from "@/entities/schema/utils/get-schema-icon";

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
    <RequireObjectPermissions objectKind={objectKind}>
      {({ permission }) => {
        return (
          <IpamDetailsLayout objectSchema={schema} objectId={objectId} permission={permission} />
        );
      }}
    </RequireObjectPermissions>
  );
};
