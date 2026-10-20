import { useParams } from "react-router";

import { NumberPoolDetailsPage } from "@/pages/resource-manager/number-pool-details";
import { ResourcePoolDetailsBody } from "@/pages/resource-manager/resource-pool-details-body";

import { queryClient } from "@/shared/api/rest/client";
import { Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import { NodeMetadataPopover } from "@/entities/nodes/object/ui/metadata/node-metadata-popover";
import { ObjectHelpButton } from "@/entities/nodes/object/ui/object-help-button";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import type { Permission } from "@/entities/permission/domain/model/permission";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";
import {
  NUMBER_POOL_KIND,
  RESOURCE_GENERIC_KIND,
} from "@/entities/resource-manager/domain/model/pool";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/ui/queries/resource-manager.query-keys";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

const ResourcePoolDetailsPage = () => {
  const { resourcePoolId } = useParams();
  const { schema: genericPoolSchema } = useSchema(RESOURCE_GENERIC_KIND);

  const { data, error, isPending } = useGetObject({
    objectSchema: genericPoolSchema!,
    objectId: resourcePoolId!,
    getAttributesVisible: () => [],
    getRelationshipsVisible: () => [],
  });

  if (isPending) return <LoadingIndicator className="h-full" />;

  if (error) return <ErrorScreen message={error.message} />;

  const objectKind = data.__typename;
  return (
    <ResourcePoolContentWithPermissions
      resourcePoolId={resourcePoolId!}
      resourcePoolKind={objectKind}
    />
  );
};

type ResourcePoolContentWithPermissionsProps = {
  resourcePoolId: string;
  resourcePoolKind: string;
};

const ResourcePoolContentWithPermissions = ({
  resourcePoolId,
  resourcePoolKind,
}: ResourcePoolContentWithPermissionsProps) => {
  const { schema } = useSchema(resourcePoolKind);

  if (!schema) return <NoDataFound />;

  return (
    <RequireObjectPermissions objectKind={schema.kind!}>
      {({ permission }) =>
        schema.kind === NUMBER_POOL_KIND ? (
          <NumberPoolDetailsPage poolId={resourcePoolId} schema={schema} permission={permission} />
        ) : (
          <ResourcePoolContent
            resourcePoolId={resourcePoolId}
            schema={schema}
            permission={permission}
          />
        )
      }
    </RequireObjectPermissions>
  );
};

type ResourcePoolContentProps = {
  resourcePoolId: string;
  schema: ModelSchema;
  permission: Permission;
};

const ResourcePoolContent = ({ resourcePoolId, schema, permission }: ResourcePoolContentProps) => {
  const resourcePoolKind = schema.kind as string;
  const {
    isPending,
    isRefetching,
    error,
    data: resourcePool,
    refetch,
  } = useGetObject({
    objectSchema: schema,
    objectId: resourcePoolId,
  });

  const handleRefetchAll = async () => {
    await Promise.all([
      refetch(),
      queryClient.invalidateQueries({
        queryKey: resourceManagerQueryKeys.all,
      }),
    ]);
  };

  if (isPending) {
    return <LoadingIndicator className="h-full" />;
  }

  if (error) {
    return <ErrorScreen message={`Error fetching resource pool: ${error.message}`} />;
  }

  return (
    <Content.Card>
      <Content.CardTitle
        title={
          <Row>
            <span>{getNodeLabel(resourcePool)}</span>
            <NodeMetadataPopover objectId={resourcePoolId} objectKind={resourcePoolKind} />
          </Row>
        }
        isReloadLoading={isRefetching}
        reload={handleRefetchAll}
        end={
          <ObjectHelpButton
            className="ml-auto"
            documentationUrl={schema.documentation}
            kind={schema.kind}
          />
        }
      />

      <ResourcePoolDetailsBody poolId={resourcePoolId} schema={schema} permission={permission} />
    </Content.Card>
  );
};

export const Component = ResourcePoolDetailsPage;
