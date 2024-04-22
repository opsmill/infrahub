import { useAtomValue } from "jotai";
import { Link, useParams } from "react-router-dom";
import { Icon } from "@iconify-icon/react";
import { genericsState, IModelSchema } from "../../../state/atoms/schema.atom";
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
      <CardWithBorder.Title>Prefix summary</CardWithBorder.Title>

      <PropertyList properties={properties} />
    </CardWithBorder>
  );
}

export default function IpamIPPrefixesSummaryDetails() {
  const { prefix } = useParams();
  const generics = useAtomValue(genericsState);

  const builtinIPPrefixSchema = generics.find(({ kind }) => kind === IP_PREFIX_DEFAULT_SCHEMA_KIND);

  const attributes = getObjectAttributes(builtinIPPrefixSchema);
  const relationships = getObjectRelationships(builtinIPPrefixSchema);

  const query = gql(
    getObjectItemsPaginated({
      kind: IP_PREFIX_DEFAULT_SCHEMA_KIND,
      attributes,
      relationships,
      filters: `prefix__value: "${prefix}"`,
    })
  );

  const { loading, data } = useQuery(query, {
    skip: !builtinIPPrefixSchema,
    notifyOnNetworkStatusChange: true,
  });

  if (loading || !data || !builtinIPPrefixSchema) return <LoadingScreen />;

  const prefixData = data[IP_PREFIX_DEFAULT_SCHEMA_KIND].edges[0].node;

  return (
    <section>
      <header className="flex items-center mb-2">
        <Link to={"/ipam/prefixes"}>All Prefixes</Link>
        <Icon icon={"mdi:chevron-right"} />
        <span>{prefix} summary</span>
      </header>

      <div className="flex items-start gap-2">
        <PrefixSummary schema={builtinIPPrefixSchema} data={prefixData} />
        <PrefixUsageChart usagePercentage={prefixData.utilization.value} />
      </div>
    </section>
  );
}
