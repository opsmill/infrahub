import { Outlet, useParams } from "react-router";

import { queryClient } from "@/shared/api/rest/client";
import { Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import ObjectEditSlideOverTrigger from "@/shared/components/form/object-edit-slide-over-trigger";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { type Property, PropertyList } from "@/shared/components/table/property-list";
import { Badge } from "@/shared/components/ui/badge";
import { Card, CardWithBorder } from "@/shared/components/ui/card";
import { Link } from "@/shared/components/ui/link";

import { IP_SUMMARY_RELATIONSHIPS_BLACKLIST } from "@/entities/ipam/constants";
import {
  type AttributeType,
  ObjectAttributeValue,
} from "@/entities/nodes/getObjectItemDisplayValue";
import { NodeMetadataPopover } from "@/entities/nodes/object/ui/object-details/node-metadata-popover";
import { ObjectHelpButton } from "@/entities/nodes/object/ui/object-help-button";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { Permission } from "@/entities/permission/types";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";
import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/constants";
import { useGetPoolUtilization } from "@/entities/resource-manager/ui/queries/get-pool-utilization.query";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/ui/queries/resource-manager.query-keys";
import ResourcePoolUtilization from "@/entities/resource-manager/ui/ResourcePoolUtilization";
import ResourceSelector from "@/entities/resource-manager/ui/resource-selector";
import type { ModelSchema } from "@/entities/schema/types";
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
      {({ permission }) => (
        <ResourcePoolContent
          resourcePoolId={resourcePoolId}
          schema={schema}
          permission={permission}
        />
      )}
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

  const {
    data: resourcePoolUtilization,
    isPending: isUtilizationPending,
    error: utilizationError,
    refetch: refetchUtilization,
  } = useGetPoolUtilization({ poolId: resourcePoolId });

  const handleRefetchAll = async () => {
    await Promise.all([
      refetch(),
      refetchUtilization(),
      // Invalidate all resource allocated queries for this pool
      queryClient.invalidateQueries({
        queryKey: resourceManagerQueryKeys.all,
      }),
    ]);
  };

  if (isPending || isUtilizationPending) {
    return <LoadingIndicator className="h-full" />;
  }

  if (error) {
    return <ErrorScreen message={`Error fetching resource pool: ${error.message}`} />;
  }

  if (utilizationError) {
    return <ErrorScreen message={`Error fetching utilization data: ${utilizationError.message}`} />;
  }

  const properties: Property[] = [
    { name: "ID", value: resourcePool.id },
    ...(schema.attributes ?? []).map((schemaAttribute) => {
      return {
        name: schemaAttribute.label || schemaAttribute.name,
        value: (
          <ObjectAttributeValue
            attributeSchema={schemaAttribute}
            attributeData={resourcePool[schemaAttribute.name] as AttributeType}
          />
        ),
      };
    }),
    {
      name: "Utilization",
      value: (
        <ResourcePoolUtilization
          utilizationOverall={resourcePoolUtilization.utilization}
          utilizationDefaultBranch={resourcePoolUtilization.utilization_default_branch}
          utilizationOtherBranches={resourcePoolUtilization.utilization_branches}
        />
      ),
    },
    ...(schema.relationships ?? [])
      .filter(({ name }) => !IP_SUMMARY_RELATIONSHIPS_BLACKLIST.includes(name))
      .map((schemaRelationship) => {
        const relationshipData = resourcePool[schemaRelationship.name]?.node;

        return {
          name: schemaRelationship.label || schemaRelationship.name,
          value: relationshipData && (
            <Link to={getObjectDetailsUrl(relationshipData.__typename, relationshipData.id)}>
              {relationshipData ? getNodeLabel(relationshipData) : ""}
            </Link>
          ),
        };
      }),
  ].filter(({ name }) => name !== "Resources");

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

      <div className="flex items-start overflow-hidden p-2">
        <aside className="mr-1 inline-flex shrink-0 flex-col gap-2">
          <Card className="shrink-0">
            <CardWithBorder.Title className="flex items-center justify-between gap-1">
              <div>
                <Badge variant="blue">{schema.namespace}</Badge> {schema.label}
              </div>

              <ObjectEditSlideOverTrigger
                data={resourcePool}
                schema={schema}
                onUpdateComplete={handleRefetchAll}
                permission={permission}
              />
            </CardWithBorder.Title>

            <PropertyList properties={properties} labelClassName="font-semibold" />
          </Card>

          <ResourceSelector resources={resourcePoolUtilization.edges.map(({ node }) => node)} />
        </aside>

        <Outlet />
      </div>
    </Content.Card>
  );
};

export const Component = ResourcePoolDetailsPage;
