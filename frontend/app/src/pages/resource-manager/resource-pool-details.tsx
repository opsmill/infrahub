import ObjectEditSlideOverTrigger from "@/components/form/object-edit-slide-over-trigger";
import { ObjectHelpButton } from "@/components/menu/object-help-button";
import { Property, PropertyList } from "@/components/table/property-list";
import { Badge } from "@/components/ui/badge";
import { CardWithBorder } from "@/components/ui/card";
import { Link } from "@/components/ui/link";
import { useObjectDetails } from "@/hooks/useObjectDetails";
import ErrorScreen from "@/screens/errors/error-screen";
import NoDataFound from "@/screens/errors/no-data-found";
import { IP_SUMMARY_RELATIONSHIPS_BLACKLIST } from "@/screens/ipam/constants";
import Content from "@/screens/layout/content";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import ResourcePoolUtilization from "@/screens/resource-manager/common/ResourcePoolUtilization";
import {
  RESOURCE_GENERIC_KIND,
  RESOURCE_POOL_UTILIZATION_KIND,
} from "@/screens/resource-manager/constants";
import {
  GET_KIND_FOR_RESOURCE_POOL,
  GET_RESOURCE_POOL_UTILIZATION,
} from "@/screens/resource-manager/graphql/resource-pool";
import ResourceSelector, { ResourceProps } from "@/screens/resource-manager/resource-selector";
import { iNodeSchema, schemaState } from "@/state/atoms/schema.atom";
import { constructPath } from "@/utils/fetch";
import { ObjectAttributeValue } from "@/utils/getObjectItemDisplayValue";
import { getObjectDetailsUrl } from "@/utils/objects";
import { useQuery } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { Outlet, useParams } from "react-router-dom";

const ResourcePoolDetailsPage = () => {
  const { resourcePoolId } = useParams();
  const nodes = useAtomValue(schemaState);

  const { data, loading } = useQuery(GET_KIND_FOR_RESOURCE_POOL, {
    variables: { ids: [resourcePoolId] },
  });

  if (loading) return <LoadingScreen />;

  const resourcePoolData = data[RESOURCE_GENERIC_KIND].edges[0];
  if (!resourcePoolData) return <NoDataFound />;

  const { id, __typename: kind } = resourcePoolData.node;
  const schema = nodes.find((node) => node.kind === kind);
  if (!schema) return <NoDataFound />;

  return <ResourcePoolContent id={id} schema={schema} />;
};

type ResourcePoolContentProps = {
  id: string;
  schema: iNodeSchema;
};

const ResourcePoolContent = ({ id, schema }: ResourcePoolContentProps) => {
  const { loading, error, data, refetch, permission } = useObjectDetails(schema, id);

  const getResourcePoolUtilizationQuery = useQuery(GET_RESOURCE_POOL_UTILIZATION, {
    variables: {
      poolId: id,
    },
  });

  if (loading || getResourcePoolUtilizationQuery.loading) return <LoadingScreen />;
  if (error || getResourcePoolUtilizationQuery.error)
    return <ErrorScreen message="Error when fetching the resource pool details" />;

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
            <Link
              to={constructPath(
                getObjectDetailsUrl(relationshipData.id, relationshipData.__typename)
              )}
            >
              {relationshipData?.display_label}
            </Link>
          ),
        };
      }),
  ].filter(({ name }) => name !== "Resources");

  return (
    <Content>
      <Content.Title
        title={
          <div className="inline-flex items-center gap-1">
            <Link to={constructPath("/resource-manager")}>Resource manager</Link>
            <Icon icon="mdi:chevron-right" />
            <span>{resourcePoolData.node.display_label}</span>
          </div>
        }
      >
        <ObjectHelpButton
          className="ml-auto"
          documentationUrl={schema.documentation}
          kind={schema.kind}
        />
      </Content.Title>

      <div className="p-2 flex items-start h-[calc(100%-64px)] overflow-hidden">
        <aside className="inline-flex flex-col gap-2 shrink-0 mr-1">
          <CardWithBorder className="shrink-0">
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
          </CardWithBorder>

          <ResourceSelector
            resources={resourcePoolUtilization.edges.map(
              ({ node }: { node: ResourceProps }) => node
            )}
          />
        </aside>

        <Outlet />
      </div>
    </Content>
  );
};

export function Component() {
  return <ResourcePoolDetailsPage />;
}
