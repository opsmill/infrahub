import { Filter } from "@/shared/hooks/useFilters";

import { ModelSchema } from "@/entities/schema/types";

export const removeFiltersNotInSchema = (filters: Filter[], schema: ModelSchema | null) => {
  if (!schema) {
    return [];
  }

  return filters.filter((filter) => {
    const [fieldName] = filter.name.split("__");
    return (
      schema.attributes?.some((attr) => attr.name === fieldName) ||
      schema.relationships?.some((rel) => rel.name === fieldName)
    );
  });
};
