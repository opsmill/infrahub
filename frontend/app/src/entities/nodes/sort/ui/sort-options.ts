import type { SortDirection, SortField } from "@/entities/nodes/sort/domain/model/sort";

export interface SortableField {
  field: SortField;
  label: string;
}

export const METADATA_SORTABLE_FIELDS: SortableField[] = [
  { field: "node_metadata__created_at", label: "Created at" },
  { field: "node_metadata__updated_at", label: "Updated at" },
];

export const DIRECTION_OPTIONS: { id: SortDirection; label: string }[] = [
  { id: "ASC", label: "Ascending" },
  { id: "DESC", label: "Descending" },
];

// "Peer › Attribute" separator. En-spaces (U+2002) around the chevron keep it from looking cramped.
export const PEER_LABEL_SEPARATOR = " › ";
