import { BranchStatus } from "@/shared/api/graphql/generated/types";

import type { FilterDefinition } from "@/entities/nodes/object/domain/filter-definition";
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
    enum: Object.values(BranchStatus),
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

export const BRANCH_FILTER_DEFINITIONS: Record<string, FilterDefinition> = {
  name: { type: "attribute", schema: BRANCH_FIELD_SCHEMAS.name },
  status: { type: "attribute", schema: BRANCH_FIELD_SCHEMAS.status },
  branched_from: { type: "attribute", schema: BRANCH_FIELD_SCHEMAS.branched_from },
  node_metadata__updated_at: {
    type: "metadata-date",
    name: "node_metadata__updated_at",
    label: "Last Update",
  },
  node_metadata__created_at: {
    type: "metadata-date",
    name: "node_metadata__created_at",
    label: "Created At",
  },
  node_metadata__created_by: {
    type: "metadata-user",
    name: "node_metadata__created_by",
    label: "Created By",
    peer: "CoreAccount",
  },
  proposed_changes: { type: "attribute", schema: BRANCH_FIELD_SCHEMAS.proposed_changes },
};
