import type { NumberPoolData } from "@/entities/resource-manager/domain/model/number-pool";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export interface AllocationScopeField {
  name: string;
  label: string;
}

export function useAllocationScopeFields(pool: NumberPoolData): AllocationScopeField[] {
  const { schema } = useSchema(pool.node.value);
  const schemaFields = [...(schema?.attributes ?? []), ...(schema?.relationships ?? [])];

  return pool.allocation_scope.value.map((name) => ({
    name,
    label: schemaFields.find((field) => field.name === name)?.label || name,
  }));
}
