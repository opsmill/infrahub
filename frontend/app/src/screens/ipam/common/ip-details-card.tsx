import ObjectEditSlideOverTrigger from "@/components/form/object-edit-slide-over-trigger";
import ProgressBarChart from "@/components/stats/progress-bar-chart";
import { Property, PropertyList } from "@/components/table/property-list";
import { Badge } from "@/components/ui/badge";
import { CardWithBorder } from "@/components/ui/card";
import { Link } from "@/components/ui/link";
import { IP_SUMMARY_RELATIONSHIPS_BLACKLIST } from "@/screens/ipam/constants";
import { Permission } from "@/screens/permission/types";
import { IModelSchema } from "@/state/atoms/schema.atom";
import { constructPath } from "@/utils/fetch";
import { AttributeType, ObjectAttributeValue } from "@/utils/getObjectItemDisplayValue";
import { getObjectDetailsUrl } from "@/utils/objects";

type tIpDetailsCard = {
  schema: IModelSchema;
  data: { id: string; display_label: string } & Record<string, AttributeType>;
  refetch: () => void;
  permission: Permission;
};

export function IpDetailsCard({ schema, data, refetch, permission }: tIpDetailsCard) {
  const properties: Property[] = [
    { name: "ID", value: data.id },
    ...(schema.attributes ?? []).map((schemaAttribute) => {
      if (schemaAttribute.name === "utilization") {
        return {
          name: schemaAttribute.label || schemaAttribute.name,
          value: <ProgressBarChart value={parseInt(data[schemaAttribute.name].value, 10)} />,
        };
      }

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
    ...(schema.relationships ?? [])
      .filter(({ name }) => !IP_SUMMARY_RELATIONSHIPS_BLACKLIST.includes(name))
      .map((schemaRelationship) => {
        const relationshipData = data[schemaRelationship.name]?.node;

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
  ];

  return (
    <CardWithBorder>
      <CardWithBorder.Title className="flex items-center justify-between gap-1">
        <div>
          <Badge variant="blue">{schema.namespace}</Badge> {schema.label} summary
        </div>
        <ObjectEditSlideOverTrigger
          data={data}
          schema={schema}
          onUpdateComplete={refetch}
          permission={permission}
        />
      </CardWithBorder.Title>

      <PropertyList properties={properties} labelClassName="font-semibold" />
    </CardWithBorder>
  );
}
