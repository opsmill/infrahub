import type { Filter } from "@/shared/hooks/useFilters";

export function isFieldFiltered(filter: Filter, fieldName: string): boolean {
  return filter.name === fieldName || filter.name.startsWith(fieldName + "__");
}
