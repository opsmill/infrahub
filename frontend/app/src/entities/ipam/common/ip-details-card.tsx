import { IP_SUMMARY_RELATIONSHIPS_BLACKLIST } from "@/entities/ipam/constants";
import { AttributeType, ObjectAttributeValue } from "@/entities/nodes/getObjectItemDisplayValue";
import { NodeRelationshipMany, NodeRelationshipOne } from "@/entities/nodes/types";
import { getObjectDetailsUrl2 } from "@/entities/nodes/utils";
import { Permission } from "@/entities/permission/types";
import { ModelSchema } from "@/entities/schema/types";
import ObjectEditSlideOverTrigger from "@/shared/components/form/object-edit-slide-over-trigger";
import ProgressBarChart from "@/shared/components/stats/progress-bar-chart";
import { Property, PropertyList } from "@/shared/components/table/property-list";
import { Badge } from "@/shared/components/ui/badge";
import { CardWithBorder } from "@/shared/components/ui/card";
import { Link } from "@/shared/components/ui/link";

type tIpDetailsCard = {
  schema: ModelSchema;
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
        const name = schemaRelationship.label || schemaRelationship.name;

        if (schemaRelationship.cardinality === "one") {
          const relationshipOneData = data[schemaRelationship.name] as
            | NodeRelationshipOne
            | undefined;

          if (!relationshipOneData) {
            return {
              name,
              value: null,
            };
          }

          const relationshipData = relationshipOneData.node;
          return {
            name,
            value: relationshipData ? (
              <Link to={getObjectDetailsUrl2(relationshipData.__typename, relationshipData.id)}>
                {relationshipData?.display_label}
              </Link>
            ) : null,
          };
        }

        const relationshipManyData = data[schemaRelationship.name] as
          | NodeRelationshipMany
          | undefined;

        if (!relationshipManyData || relationshipManyData.edges.length === 0) {
          return {
            name,
            value: null,
          };
        }

        return {
          name,
          value: (
            <div className="flex flex-col">
              {relationshipManyData?.edges?.map(({ node }) => {
                if (!node) return null;

                return (
                  <Link key={node?.id} to={getObjectDetailsUrl2(node.__typename, node.id)}>
                    {node.display_label}
                  </Link>
                );
              })}
            </div>
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
