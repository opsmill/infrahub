import { OrderDirection } from "@/shared/api/graphql/generated/types";

export type SortField = `${string}__${string}`;
export type SortDirection = OrderDirection;
export type SortToken = `${SortField}__${Lowercase<SortDirection>}`;

export interface Sort {
  field: SortField;
  direction: SortDirection;
}

export const SORT_DIRECTION = OrderDirection;

export const NODE_METADATA_SORT_FIELDS = [
  "node_metadata__created_at",
  "node_metadata__updated_at",
] as const satisfies SortField[];

export type NodeMetadataSortField = (typeof NODE_METADATA_SORT_FIELDS)[number];
