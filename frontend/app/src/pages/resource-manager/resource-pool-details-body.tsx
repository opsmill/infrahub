import { Card, CardHeader } from "@infrahub/ui";
import { Outlet } from "react-router";

import { queryClient } from "@/shared/api/rest/client";
import ErrorScreen from "@/shared/components/errors/error-screen";
import ObjectEditSlideOverTrigger from "@/shared/components/form/object-edit-slide-over-trigger";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { type Property, PropertyList } from "@/shared/components/table/property-list";
import { Badge } from "@/shared/components/ui/badge";
import { Link } from "@/shared/components/ui/link";

import { ObjectAttributeValue } from "@/entities/nodes/getObjectItemDisplayValue";
import type { NodeAttributeWithMetadata } from "@/entities/nodes/object/domain/model/node";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import { isNodeRelationshipOne } from "@/entities/nodes/object/domain/rules/is-node-relationship-one";
import { isRelationshipVisibleInSummary } from "@/entities/nodes/object/domain/rules/is-relationship-visible-in-summary";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import type { Permission } from "@/entities/permission/domain/model/permission";
import { useGetPoolUtilization } from "@/entities/resource-manager/ui/queries/get-pool-utilization.query";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/ui/queries/resource-manager.query-keys";
import ResourcePoolUtilization from "@/entities/resource-manager/ui/ResourcePoolUtilization";
import ResourceSelector from "@/entities/resource-manager/ui/resource-selector";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

export interface ResourcePoolDetailsBodyProps {
  poolId: string;
  schema: ModelSchema;
  permission: Permission;
}

export function ResourcePoolDetailsBody({
  poolId,
  schema,
  permission,
}: ResourcePoolDetailsBodyProps) {
  const {
    isPending,
    error,
    data: resourcePool,
    refetch,
  } = useGetObject({
    objectSchema: schema,
    objectId: poolId,
  });

  const {
    data: resourcePoolUtilization,
    isPending: isUtilizationPending,
    error: utilizationError,
    refetch: refetchUtilization,
  } = useGetPoolUtilization({ poolId });

  const handleRefetchAll = async () => {
    await Promise.all([
      refetch(),
      refetchUtilization(),
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
            attributeData={resourcePool[schemaAttribute.name] as NodeAttributeWithMetadata}
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
      .filter(isRelationshipVisibleInSummary)
      .map((schemaRelationship) => {
        const relationship = resourcePool[schemaRelationship.name];
        const relationshipData = isNodeRelationshipOne(relationship) ? relationship.node : null;

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
    <div className="flex items-start overflow-hidden p-2">
      <aside className="mr-1 inline-flex shrink-0 flex-col gap-2">
        <Card className="shrink-0">
          <CardHeader className="flex items-center justify-between gap-1">
            <Badge variant="blue">{schema.namespace}</Badge>
            <span>{schema.label}</span>
            <ObjectEditSlideOverTrigger
              data={resourcePool}
              schema={schema}
              onUpdateComplete={handleRefetchAll}
              permission={permission}
            />
          </CardHeader>

          <PropertyList properties={properties} labelClassName="font-semibold" />
        </Card>

        <ResourceSelector resources={resourcePoolUtilization.edges.map(({ node }) => node)} />
      </aside>

      <Outlet />
    </div>
  );
}
