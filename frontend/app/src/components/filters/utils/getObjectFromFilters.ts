import { Filter } from "@/hooks/useFilters";
import { IModelSchema } from "@/state/atoms/schema.atom";
import {
  AttributeType,
  Node,
  RelationshipManyType,
  RelationshipOneType,
  RelationshipType,
} from "@/utils/getObjectItemDisplayValue";

export const getObjectFromFilters = (
  schema: IModelSchema,
  filters: Array<Filter>
): Record<string, AttributeType | RelationshipType> => {
  return filters.reduce(
    (acc, filter) => {
      const [fieldName, fieldKey] = filter.name.split("__");

      if (fieldKey === "value") {
        return {
          ...acc,
          [fieldName]: { value: filter.value } satisfies AttributeType,
        };
      }

      if (fieldKey === "ids") {
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
              node: { id: filter.value[0], display_label: "", __typename: relationshipSchema.peer },
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
