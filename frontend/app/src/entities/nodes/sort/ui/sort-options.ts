import type {
  NodeMetadataSortField,
  SortDirection,
  SortField,
} from "@/entities/nodes/sort/domain/model/sort";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/domain/model/schema";

export interface SortableField {
  field: SortField;
  label: string;
  /** Schema field the sort field originates from (absent for node metadata). */
  fieldSchema?: AttributeSchema | RelationshipSchema;
}

export const NODE_METADATA_SORT_OPTIONS: SortableField[] = [
  { field: "node_metadata__created_at", label: "Created at" },
  { field: "node_metadata__updated_at", label: "Updated at" },
] satisfies { field: NodeMetadataSortField; label: string }[];

// "Peer › Attribute" separator. En-spaces (U+2002) around the chevron keep it from looking cramped.
export const PEER_LABEL_SEPARATOR = " › ";

export const DIRECTION_OPTIONS: { id: SortDirection; label: string }[] = [
  { id: "ASC", label: "Ascending" },
  { id: "DESC", label: "Descending" },
];
