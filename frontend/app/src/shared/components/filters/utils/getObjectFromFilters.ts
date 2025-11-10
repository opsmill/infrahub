import type { Filter } from "@/shared/hooks/useFilters";

import type {
  AttributeType,
  Node,
  RelationshipManyType,
  RelationshipOneType,
  RelationshipType,
} from "@/entities/nodes/getObjectItemDisplayValue";
import type { ModelSchema } from "@/entities/schema/types";

export const getObjectFromFilters = (
  schema: ModelSchema | null,
  filters: Array<Filter>
): Record<string, AttributeType | RelationshipType> => {
  return filters.reduce(
    (acc, filter) => {
      const [fieldName, fieldKey] = filter.name.split("__");

      if (!fieldName || !fieldKey) {
        return acc;
      }

      if (fieldKey === "value") {
        return {
          ...acc,
          [fieldName]: { value: filter.value } satisfies AttributeType,
        };
      }

      if (fieldKey === "values") {
        return {
          ...acc,
          [fieldName]: { value: filter.value } satisfies AttributeType,
        };
      }

      if (fieldKey === "ids" && schema) {
        const relationshipSchema = schema.relationships?.find(({ name }) => name === fieldName);
        if (!relationshipSchema) return acc;

        if (relationshipSchema.cardinality === "many") {
          return {
            ...acc,
            [fieldName]: {
              edges: filter.value.map(
                (v: Node) =>
                  ({
                    node: {
                      id: v.id,
                      display_label: v.display_label,
                      __typename: relationshipSchema.peer,
                    },
                  }) satisfies RelationshipOneType
              ),
            } satisfies RelationshipManyType,
          };
        }

        if (relationshipSchema.cardinality === "one") {
          return {
            ...acc,
            [fieldName]: {
              node: { ...filter.value[0] },
            } satisfies RelationshipOneType,
          };
        }

        return acc;
      }

      return acc;
    },
    {} as Record<string, AttributeType | RelationshipType>
  );
};
