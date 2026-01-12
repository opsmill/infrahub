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
  updated_at: {
    name: "updated_at",
    label: "Last Update",
    kind: "DateTime",
  } as AttributeSchema,
  created_at: {
    name: "created_at",
    label: "Created At",
    kind: "DateTime",
  } as AttributeSchema,
  created_by: {
    name: "created_by",
    label: "Created By",
    peer: "CoreAccount",
  } as RelationshipSchema,
} as const;
