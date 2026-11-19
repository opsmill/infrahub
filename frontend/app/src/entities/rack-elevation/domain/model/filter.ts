export interface FilterCondition {
  key: string;
  value: string;
}

export interface ItemFilter {
  query: string;
  conditions: FilterCondition[];
}

export interface Facet {
  key: string;
  label: string;
  values: { value: string; count: number }[];
}

export function isFilterActive(filter: ItemFilter): boolean {
  return filter.query.trim() !== "" || filter.conditions.length > 0;
}
