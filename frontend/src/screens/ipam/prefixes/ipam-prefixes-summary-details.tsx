import { useAtomValue } from "jotai";
import { Link, useParams } from "react-router-dom";
import { Icon } from "@iconify-icon/react";
import { genericsState, IModelSchema, schemaState } from "../../../state/atoms/schema.atom";
import { PrefixUsageChart } from "../common/prefix-usage-chart";
import LoadingScreen from "../../loading-screen/loading-screen";
import { IP_PREFIX_DEFAULT_SCHEMA_KIND } from "../constants";
import { getObjectAttributes, getObjectRelationships } from "../../../utils/getSchemaObjectColumns";
import { getObjectItemsPaginated } from "../../../graphql/queries/objects/getObjectItems";
import { gql } from "@apollo/client";
import useQuery from "../../../hooks/useQuery";
import { CardWithBorder } from "../../../components/ui/card";
import { AttributeType, ObjectAttributeValue } from "../../../utils/getObjectItemDisplayValue";
import { Property, PropertyList } from "../../../components/table/property-list";
import { GET_PREFIX_KIND } from "../../../graphql/queries/ipam/prefixes";
import { Badge } from "../../../components/ui/badge";

function PrefixSummary({
  schema,
  data,
}: {
  schema: IModelSchema;
  data: { id: string } & Record<string, AttributeType>;
}) {
  const schemaPropertiesOrdered = [
    ...(schema.attributes ?? []),
    ...(schema.relationships ?? []),
  ].sort((a, b) => (a.order_weight ?? 0) - (b.order_weight ?? 0));

  const properties: Property[] = [
    { name: "ID", value: data.id },
    ...schemaPropertiesOrdered.map((schemaProperty) => ({
      name: schemaProperty.label || schemaProperty.name,
      value: (
        <ObjectAttributeValue
          attributeSchema={schemaProperty}
          attributeValue={data[schemaProperty.name] ?? "-"}
        />
      ),
    })),
  ];

  return (
    <CardWithBorder>
      <CardWithBorder.Title>
        <div className="flex justify-between">
          <h4>Prefix summary</h4>
          <div className="space-x-1">
            <Badge variant="blue">{schema.namespace}</Badge>
            <span className="text-sm">{schema.name}</span>
          </div>
        </div>
      </CardWithBorder.Title>

      <PropertyList properties={properties} />
    </CardWithBorder>
  );
}

export default function IpamIPPrefixesSummaryDetails() {
  const { prefix } = useParams();

  const { loading, data } = useQuery(GET_PREFIX_KIND, {
    variables: {
      ip: prefix,
    },
  });

  if (loading || !data) return <LoadingScreen />;

  const prefixKind = data[IP_PREFIX_DEFAULT_SCHEMA_KIND].edges[0].node.__typename;

  return (
    <section>
      <header className="flex items-center mb-2">
        <Link to={"/ipam/prefixes"}>All Prefixes</Link>
        <Icon icon={"mdi:chevron-right"} />
        <span>{prefix} summary</span>
      </header>

      <PrefixSummaryContent prefixKind={prefixKind} />
    </section>
  );
}

const PrefixSummaryContent = ({ prefixKind }: { prefixKind: string }) => {
  const { prefix } = useParams();
  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);

  const prefixSchema = [...nodes, ...generics].find(({ kind }) => kind === prefixKind);

  const attributes = getObjectAttributes(prefixSchema);
  const relationships = getObjectRelationships(prefixSchema);

  const query = gql(
    getObjectItemsPaginated({
      kind: prefixKind,
      attributes,
      relationships,
      filters: `prefix__value: "${prefix}"`,
    })
  );

  const { loading, data } = useQuery(query, {
    skip: !prefixSchema,
    notifyOnNetworkStatusChange: true,
  });

  if (loading || !data || !prefixSchema) return <LoadingScreen />;

  const prefixData = data[prefixKind].edges[0].node;

  return (
    <div className="flex items-start gap-2">
      <PrefixSummary schema={prefixSchema} data={prefixData} />
      <PrefixUsageChart usagePercentage={prefixData.utilization.value} />
    </div>
  );
};
