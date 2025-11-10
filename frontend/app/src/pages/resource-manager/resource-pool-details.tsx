import { useQuery } from "@apollo/client";
import { useAtomValue } from "jotai";
import { Outlet, useParams } from "react-router";

import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import ObjectEditSlideOverTrigger from "@/shared/components/form/object-edit-slide-over-trigger";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ObjectHelpButton } from "@/shared/components/menu/object-help-button";
import { type Property, PropertyList } from "@/shared/components/table/property-list";
import { Badge } from "@/shared/components/ui/badge";
import { Card, CardWithBorder } from "@/shared/components/ui/card";
import { Link } from "@/shared/components/ui/link";

import { IP_SUMMARY_RELATIONSHIPS_BLACKLIST } from "@/entities/ipam/constants";
import { ObjectAttributeValue } from "@/entities/nodes/getObjectItemDisplayValue";
import { useObjectDetails } from "@/entities/nodes/hooks/useObjectDetails";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import {
  GET_KIND_FOR_RESOURCE_POOL,
  GET_RESOURCE_POOL_UTILIZATION,
} from "@/entities/resource-manager/api/resource-pool";
import {
  RESOURCE_GENERIC_KIND,
  RESOURCE_POOL_UTILIZATION_KIND,
} from "@/entities/resource-manager/constants";
import ResourcePoolUtilization from "@/entities/resource-manager/ui/ResourcePoolUtilization";
import ResourceSelector, {
  type ResourceProps,
} from "@/entities/resource-manager/ui/resource-selector";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import type { NodeSchema } from "@/entities/schema/types";

const ResourcePoolDetailsPage = () => {
  const { resourcePoolId } = useParams();
  const nodes = useAtomValue(nodeSchemasAtom);

  const { data, loading } = useQuery(GET_KIND_FOR_RESOURCE_POOL, {
    variables: { ids: [resourcePoolId] },
  });

  if (loading) return <LoadingIndicator className="h-full" />;

  const resourcePoolData = data[RESOURCE_GENERIC_KIND].edges[0];
  if (!resourcePoolData) return <NoDataFound />;

  const { id, __typename: kind } = resourcePoolData.node;
  const schema = nodes.find((node) => node.kind === kind);
  if (!schema) return <NoDataFound />;

  return <ResourcePoolContent id={id} schema={schema} />;
};

type ResourcePoolContentProps = {
  id: string;
  schema: NodeSchema;
};

const ResourcePoolContent = ({ id, schema }: ResourcePoolContentProps) => {
  const { loading, error, data, refetch, permission } = useObjectDetails(schema, id);

  const getResourcePoolUtilizationQuery = useQuery(GET_RESOURCE_POOL_UTILIZATION, {
    variables: {
      poolId: id,
    },
  });

  if (loading || getResourcePoolUtilizationQuery.loading) {
    return <LoadingIndicator className="h-full" />;
  }

  if (error || getResourcePoolUtilizationQuery.error) {
    return <ErrorScreen message="Error when fetching the resource pool details" />;
  }

  const resourcePoolData = data[schema.kind!].edges[0];
  if (!resourcePoolData) return <NoDataFound />;

  const resourcePool = resourcePoolData.node;
  const resourcePoolUtilization =
    getResourcePoolUtilizationQuery.data[RESOURCE_POOL_UTILIZATION_KIND];

  const properties: Property[] = [
    { name: "ID", value: resourcePool.id },
    ...(schema.attributes ?? []).map((schemaAttribute) => {
      return {
        name: schemaAttribute.label || schemaAttribute.name,
        value: (
          <ObjectAttributeValue
            attributeSchema={schemaAttribute}
            attributeValue={resourcePool[schemaAttribute.name]}
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
              {relationshipData?.display_label}
            </Link>
          ),
        };
      }),
  ].filter(({ name }) => name !== "Resources");

  return (
    <Content.Card>
      <Content.CardTitle
        title={resourcePoolData.node.display_label}
        isReloadLoading={loading}
        reload={() => {
          refetch();
          getResourcePoolUtilizationQuery.refetch();
        }}
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
                onUpdateComplete={() => {
                  refetch();
                  getResourcePoolUtilizationQuery.refetch();
                }}
                permission={permission}
              />
            </CardWithBorder.Title>

            <PropertyList properties={properties} labelClassName="font-semibold" />
          </Card>

          <ResourceSelector
            resources={resourcePoolUtilization.edges.map(
              ({ node }: { node: ResourceProps }) => node
            )}
          />
        </aside>

        <Outlet />
      </div>
    </Content.Card>
  );
};

export function Component() {
  return <ResourcePoolDetailsPage />;
}
