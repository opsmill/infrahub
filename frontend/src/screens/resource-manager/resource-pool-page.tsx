import { useAtomValue } from "jotai";
import { Outlet, useParams } from "react-router-dom";
import Content from "../layout/content";
import { ObjectHelpButton } from "../../components/menu/object-help-button";
import { iNodeSchema, schemaState } from "../../state/atoms/schema.atom";
import { gql, useQuery } from "@apollo/client";
import { GET_KIND_FOR_RESOURCE_POOL, GET_RESOURCE_POOL_UTILIZATION } from "./graphql/resource-pool";
import LoadingScreen from "../loading-screen/loading-screen";
import { RESOURCE_GENERIC_KIND, RESOURCE_POOL_UTILIZATION_KIND } from "./constants";
import NoDataFound from "../errors/no-data-found";
import { getSchemaObjectColumns, getTabs } from "../../utils/getSchemaObjectColumns";
import { getObjectDetailsPaginated } from "../../graphql/queries/objects/getObjectDetails";
import { DEFAULT_BRANCH_NAME, TASK_OBJECT } from "../../config/constants";
import ErrorScreen from "../errors/error-screen";
import { Icon } from "@iconify-icon/react";
import { constructPath } from "../../utils/fetch";
import { Link } from "../../components/utils/link";
import { CardWithBorder } from "../../components/ui/card";
import { Property, PropertyList } from "../../components/table/property-list";
import { ObjectAttributeValue } from "../../utils/getObjectItemDisplayValue";
import { IP_SUMMARY_RELATIONSHIPS_BLACKLIST } from "../ipam/constants";
import { getObjectDetailsUrl } from "../../utils/objects";
import { Badge } from "../../components/ui/badge";
import { ButtonWithTooltip } from "../../components/buttons/button-primitive";
import { usePermission } from "../../hooks/usePermission";
import { useState } from "react";
import ObjectItemEditComponent from "../object-item-edit/object-item-edit-paginated";
import SlideOver from "../../components/display/slide-over";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import ResourceSelector, { ResourceProps } from "./resource-selector";
import ResourcePoolUtilization from "./common/ResourcePoolUtilization";

const ResourcePoolPage = () => {
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
  const permission = usePermission();
  const branch = useAtomValue(currentBranchAtom);
  const [showEditDrawer, setShowEditDrawer] = useState(false);

  const columns = getSchemaObjectColumns({ schema });
  const relationshipsTabs = getTabs(schema);

  const query = gql(
    getObjectDetailsPaginated({
      objectid: id,
      kind: schema.kind,
      taskKind: TASK_OBJECT,
      columns,
      relationshipsTabs,
      queryProfiles: true,
    })
  );

  const { loading, error, data, refetch } = useQuery(query);
  const getResourcePoolUtilizationQuery = useQuery(GET_RESOURCE_POOL_UTILIZATION, {
    variables: {
      poolId: id,
    },
  });

  if (loading || getResourcePoolUtilizationQuery.loading) return <LoadingScreen />;
  if (error) return <ErrorScreen message="Error when fetching the resource pool details" />;

  const resourcePoolData = data[schema.kind!].edges[0];
  if (!resourcePoolData) return <NoDataFound />;

  const resourcePool = resourcePoolData.node;
  const resourcePoolUtilization =
    getResourcePoolUtilizationQuery.data[RESOURCE_POOL_UTILIZATION_KIND];

  const properties: Property[] = [
    { name: "ID", value: resourcePool.id },
    ...(schema.attributes ?? []).map((schemaAttribute) => {
      if (schemaAttribute.name === "utilization") {
        return {
          name: schemaAttribute.label || schemaAttribute.name,
          value: (
            <ResourcePoolUtilization
              utilizationOverall={resourcePoolUtilization.utilization}
              utilizationDefaultBranch={resourcePoolUtilization.utilization_default_branch}
              utilizationOtherBranches={resourcePoolUtilization.utilization_branches}
            />
          ),
        };
      }

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
              )}>
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
        }>
        <ObjectHelpButton
          className="ml-auto"
          documentationUrl={schema.documentation}
          kind={schema.kind}
        />
      </Content.Title>

      <div className="p-2 gap-2 flex">
        <aside className="inline-flex flex-col gap-2">
          <CardWithBorder>
            <CardWithBorder.Title className="flex items-center justify-between gap-1">
              <div>
                <Badge variant="blue">{schema.namespace}</Badge> {schema.label}
              </div>
              <ButtonWithTooltip
                variant="outline"
                size="icon"
                onClick={() => setShowEditDrawer(true)}
                disabled={!permission.write.allow}
                tooltipEnabled={!permission.write.allow}
                tooltipContent={permission.write.message ?? undefined}
                data-testid="pool-edit-button">
                <Icon icon="mdi:pencil" />
              </ButtonWithTooltip>
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

      <SlideOver
        title={
          <div className="space-y-2">
            <div className="flex items-start">
              <div className="flex-grow flex items-center flex-wrap overflow-hidden">
                <span className="font-semibold text-gray-900 truncate">{schema.label}</span>

                <Icon icon="mdi:chevron-right" />

                <span className="flex-grow text-gray-500 overflow-hidden break-words line-clamp-3">
                  {resourcePool.display_label}
                </span>
              </div>

              <div className="flex items-center ml-3">
                <Icon icon="mdi:layers-triple" />
                <span className="ml-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</span>
              </div>
            </div>

            <div className="">{schema?.description}</div>

            <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20 mr-2">
              <svg
                className="h-1.5 w-1.5 mr-1 fill-yellow-500"
                viewBox="0 0 6 6"
                aria-hidden="true">
                <circle cx={3} cy={3} r={3} />
              </svg>
              {schema.kind}
            </span>
            <div className="inline-flex items-center rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-custom-blue-500 ring-1 ring-inset ring-custom-blue-500/10">
              <svg
                className="h-1.5 w-1.5 mr-1 fill-custom-blue-500"
                viewBox="0 0 6 6"
                aria-hidden="true">
                <circle cx={3} cy={3} r={3} />
              </svg>
              ID: {resourcePool.id}
            </div>
          </div>
        }
        open={showEditDrawer}
        setOpen={setShowEditDrawer}>
        <ObjectItemEditComponent
          closeDrawer={() => setShowEditDrawer(false)}
          onUpdateComplete={() => {
            refetch();
            getResourcePoolUtilizationQuery.refetch();
          }}
          objectid={resourcePool.id as string}
          objectname={schema.kind as string}
        />
      </SlideOver>
    </Content>
  );
};

export default ResourcePoolPage;
