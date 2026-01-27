import { BRANCH_STATUS } from "@/entities/branches/constants";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

export const BRANCH_FIELD_SCHEMAS = {
  name: {
    name: "name",
    label: "Branch",
    kind: "Text",
  } as AttributeSchema,
  status: {
    name: "status",
    label: "Status",
    kind: "Text",
    enum: Object.values(BRANCH_STATUS),
  } as AttributeSchema,
  branched_from: {
    name: "branched_from",
    label: "Last Rebase",
    kind: "DateTime",
  } as AttributeSchema,
  node_metadata__updated_at: {
    name: "node_metadata__updated_at",
    label: "Last Update",
    kind: "DateTime",
  } as AttributeSchema,
  node_metadata__created_at: {
    name: "node_metadata__created_at",
    label: "Created At",
    kind: "DateTime",
  } as AttributeSchema,
  node_metadata__created_by: {
    name: "node_metadata__created_by",
    label: "Created By",
    peer: "CoreAccount",
  } as RelationshipSchema,
  proposed_changes: {
    name: "proposed_changes",
    label: "Proposed Changes",
    kind: "Text",
  } as AttributeSchema,
} as const;
