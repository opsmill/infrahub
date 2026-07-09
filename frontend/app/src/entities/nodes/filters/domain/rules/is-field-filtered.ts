import type { Filter } from "@/entities/nodes/filters/domain/model/filter";

export function isFieldFiltered(filter: Filter, fieldName: string): boolean {
  return filter.name === fieldName || filter.name.startsWith(fieldName + "__");
}
