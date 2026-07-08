import { OrderDirection } from "@/shared/api/graphql/generated/types";

export type SortField = `${string}__${string}`;
export type SortDirection = OrderDirection;
export type SortToken = `${SortField}__${Lowercase<SortDirection>}`;

export interface Sort {
  field: SortField;
  direction: SortDirection;
}

export interface SortableField {
  field: SortField;
  label: string;
}

export const SORT_DIRECTION = OrderDirection;
