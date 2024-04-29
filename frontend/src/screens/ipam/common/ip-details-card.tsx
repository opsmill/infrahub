import { Property, PropertyList } from "../../../components/table/property-list";
import { Badge } from "../../../components/ui/badge";
import { CardWithBorder } from "../../../components/ui/card";
import { Link } from "../../../components/utils/link";
import { IModelSchema } from "../../../state/atoms/schema.atom";
import { constructPath } from "../../../utils/fetch";
import { AttributeType, ObjectAttributeValue } from "../../../utils/getObjectItemDisplayValue";
import { getObjectDetailsUrl } from "../../../utils/objects";
import { IP_SUMMARY_RELATIONSHIPS_BLACKLIST } from "../constants";

export function IpDetailsCard({
  schema,
  data,
}: {
  schema: IModelSchema;
  data: { id: string } & Record<string, AttributeType>;
}) {
  const properties: (Property | undefined)[] = [
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
    ...(schema.relationships ?? []).map((schemaRelationship) => {
      if (IP_SUMMARY_RELATIONSHIPS_BLACKLIST.includes(schemaRelationship.name)) return;

      const relationshipData = data[schemaRelationship.name]?.node;

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
