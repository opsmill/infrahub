import { useAtomValue } from "jotai";
import { useParams } from "react-router-dom";
import Content from "../layout/content";
import { ObjectHelpButton } from "../../components/menu/object-help-button";
import { iNodeSchema, schemaState } from "../../state/atoms/schema.atom";
import { gql, useQuery } from "@apollo/client";
import { GET_KIND_FOR_RESOURCE_POOL } from "./graphql/resource-pool";
import LoadingScreen from "../loading-screen/loading-screen";
import { RESOURCE_GENERIC_KIND } from "./constants";
import NoDataFound from "../errors/no-data-found";
import { getSchemaObjectColumns, getTabs } from "../../utils/getSchemaObjectColumns";
import { getObjectDetailsPaginated } from "../../graphql/queries/objects/getObjectDetails";
import { TASK_OBJECT } from "../../config/constants";
import ErrorScreen from "../errors/error-screen";
import { Icon } from "@iconify-icon/react";
import { constructPath } from "../../utils/fetch";
import { Link } from "../../components/utils/link";
import { CardWithBorder } from "../../components/ui/card";
import { Property, PropertyList } from "../../components/table/property-list";
import ProgressBarChart from "../../components/stats/progress-bar-chart";
import { ObjectAttributeValue } from "../../utils/getObjectItemDisplayValue";
import { IP_SUMMARY_RELATIONSHIPS_BLACKLIST } from "../ipam/constants";
import { getObjectDetailsUrl } from "../../utils/objects";

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

  const { loading, error, data } = useQuery(query);

  if (loading) return <LoadingScreen />;
  if (error) return <ErrorScreen message="Error when fetching the resource pool details" />;

  const resourcePoolData = data[schema.kind!].edges[0];
  if (!resourcePoolData) return <NoDataFound />;

  const resourcePool = resourcePoolData.node;

  const properties: Property[] = [
    { name: "ID", value: resourcePool.id },
    ...(schema.attributes ?? []).map((schemaAttribute) => {
      if (schemaAttribute.name === "utilization") {
        return {
          name: schemaAttribute.label || schemaAttribute.name,
          value: (
            <ProgressBarChart value={parseInt(resourcePool[schemaAttribute.name].value, 10)} />
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

      <main className="p-2 flex">
        <CardWithBorder>
          <PropertyList properties={properties} labelClassName="font-semibold" />
        </CardWithBorder>
      </main>
    </Content>
  );
};

export default ResourcePoolPage;
