import { IModelSchema } from "../../../state/atoms/schema.atom";
import { AttributeType, ObjectAttributeValue } from "../../../utils/getObjectItemDisplayValue";
import { Property, PropertyList } from "../../../components/table/property-list";
import { CardWithBorder } from "../../../components/ui/card";
import { Badge } from "../../../components/ui/badge";
import { Link } from "../../../components/utils/link";
import { constructPath } from "../../../utils/fetch";
import { getObjectDetailsUrl } from "../../../utils/objects";

export function IpDetailsCard({
  schema,
  data,
}: {
  schema: IModelSchema;
  data: { id: string } & Record<string, AttributeType>;
}) {
  const properties: Property[] = [
    { name: "ID", value: data.id },
    ...(schema.attributes ?? []).map((schemaAttribute) => {
      return {
        name: schemaAttribute.label || schemaAttribute.name,
        value: (
          <ObjectAttributeValue
            attributeSchema={schemaAttribute}
            attributeValue={data[schemaAttribute.name]}
          />
        ),
      };
    }),
    ...(schema.relationships ?? []).map((schemaAttribute) => {
      const relationshipData = data[schemaAttribute.name]?.node;
      console.log(relationshipData);
      return {
        name: schemaAttribute.label || schemaAttribute.name,
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
  ];

  return (
    <CardWithBorder>
      <CardWithBorder.Title className="flex items-center gap-1">
        <Badge variant="blue">{schema.namespace}</Badge> {schema.name} summary
      </CardWithBorder.Title>

      <PropertyList properties={properties} labelClassName="font-semibold" />
    </CardWithBorder>
  );
}
