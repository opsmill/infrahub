import { IModelSchema } from "../../../state/atoms/schema.atom";
import { AttributeType, ObjectAttributeValue } from "../../../utils/getObjectItemDisplayValue";
import { Property, PropertyList } from "../../../components/table/property-list";
import { CardWithBorder } from "../../../components/ui/card";
import { Badge } from "../../../components/ui/badge";

export function IpDetailsCard({
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
      <CardWithBorder.Title className="flex items-center gap-1">
        <Badge variant="blue">{schema.namespace}</Badge> {schema.name} summary
      </CardWithBorder.Title>

      <PropertyList properties={properties} />
    </CardWithBorder>
  );
}
