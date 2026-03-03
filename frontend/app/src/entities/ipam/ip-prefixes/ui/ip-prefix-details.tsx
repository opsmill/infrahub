import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import ProgressBarChart from "@/shared/components/stats/progress-bar-chart";
import { type Property, PropertyList } from "@/shared/components/table/property-list";
import { Link } from "@/shared/components/ui/link";

import { IP_SUMMARY_RELATIONSHIPS_BLACKLIST } from "@/entities/ipam/constants";
import { ObjectAttributeValue } from "@/entities/nodes/getObjectItemDisplayValue";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { isRelationshipVisibleInDetailedView } from "@/entities/nodes/object/utils/get-relationships-visible-in-detailed-view";
import type {
  NodeAttribute,
  NodeRelationshipMany,
  NodeRelationshipOne,
} from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { ModelSchema } from "@/entities/schema/types";

export interface IpPrefixDetailsProps {
  prefixSchema: ModelSchema;
  prefixId: string;
}

export function IpPrefixDetails({ prefixSchema, prefixId }: IpPrefixDetailsProps) {
  const { isPending, error, data } = useGetObject({
    objectSchema: prefixSchema,
    objectId: prefixId,
    getRelationshipsVisible: (relationships) =>
      relationships.filter((rel) => {
        if (rel.cardinality === "one") return true;
        return isRelationshipVisibleInDetailedView(rel);
      }),
  });

  if (isPending) {
    return <LoadingIndicator className="h-full" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const properties: Property[] = [
    { name: "ID", value: data.id },
    ...(prefixSchema.attributes ?? []).map((schemaAttribute) => {
      const attributeData = data[schemaAttribute.name] as NodeAttribute | undefined;

      if (
        !attributeData ||
        (!attributeData.value && attributeData.value !== 0 && attributeData.value !== false)
      ) {
        return {
          name: schemaAttribute.label || schemaAttribute.name,
          value: "-",
        };
      }

      if (schemaAttribute.name === "utilization") {
        return {
          name: schemaAttribute.label || schemaAttribute.name,
          value: <ProgressBarChart value={parseInt(attributeData.value.toString(), 10)} />,
        };
      }

      return {
        name: schemaAttribute.label || schemaAttribute.name,
        value: (
          <ObjectAttributeValue attributeSchema={schemaAttribute} attributeData={attributeData} />
        ),
      };
    }),
    ...(prefixSchema.relationships ?? [])
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
              <Link to={getObjectDetailsUrl(relationshipData.__typename, relationshipData.id)}>
                {getNodeLabel(relationshipData)}
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
                  <Link key={node?.id} to={getObjectDetailsUrl(node.__typename, node.id)}>
                    {getNodeLabel(node)}
                  </Link>
                );
              })}
            </div>
          ),
        };
      }),
  ];

  return <PropertyList properties={properties} labelClassName="font-semibold" />;
}
