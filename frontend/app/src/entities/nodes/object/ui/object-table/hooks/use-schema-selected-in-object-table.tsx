import { getSchema } from "@/entities/schema/domain/get-schema";
import { ModelSchema } from "@/entities/schema/types";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";
import useFilters from "@/shared/hooks/useFilters";
import React from "react";

export const useSchemaSelectedInObjectTable = (schema: ModelSchema) => {
  const [filters] = useFilters();
  const kindFilter = filters?.find((filter) => filter.name === "kind__value");

  return React.useMemo<ModelSchema>(() => {
    if (!isGenericSchema(schema)) return schema;

    if (!kindFilter) return schema;

    const inheritingKindInFilter = schema.used_by?.find((kind) => kind === kindFilter.value);
    if (!inheritingKindInFilter) return schema;

    const { schema: schemaOfInheritingKindInFilter } = getSchema(inheritingKindInFilter);
    if (!schemaOfInheritingKindInFilter) return schema;

    return schemaOfInheritingKindInFilter;
  }, [kindFilter, schema]);
};
