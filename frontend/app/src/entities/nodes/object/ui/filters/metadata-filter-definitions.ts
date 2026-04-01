import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

export const NODE_METADATA_PREFIX = "node_metadata__";

export const METADATA_CREATED_AT: AttributeSchema = {
  id: null,
  state: "present",
  name: "node_metadata__created_at",
  kind: ATTRIBUTE_KIND.DATETIME,
  label: "Created At",
  description: "Date and time when the node was created",
  enum: null,
  computed_attribute: null,
  choices: null,
  regex: null,
  max_length: null,
  min_length: null,
  read_only: true,
  unique: false,
  optional: true,
  branch: "aware",
  order_weight: 0,
  default_value: null,
  inherited: false,
  allow_override: "any",
  display: "default",
  deprecation: null,
  parameters: { id: null, state: "present" },
};

export const METADATA_UPDATED_AT: AttributeSchema = {
  ...METADATA_CREATED_AT,
  name: "node_metadata__updated_at",
  label: "Updated At",
  description: "Date and time when the node was last updated",
};

export const METADATA_CREATED_BY: RelationshipSchema = {
  id: null,
  state: "present",
  name: "node_metadata__created_by",
  peer: "CoreAccount",
  kind: "Attribute",
  label: "Created By",
  description: "Account that created the node",
  identifier: null,
  cardinality: "one",
  min_count: 0,
  max_count: 0,
  order_weight: 0,
  optional: true,
  branch: "aware",
  inherited: false,
  direction: "bidirectional",
  hierarchical: null,
  on_delete: "no-action",
  allow_override: "any",
  read_only: true,
  display: "default",
  deprecation: null,
};

export const METADATA_UPDATED_BY: RelationshipSchema = {
  ...METADATA_CREATED_BY,
  name: "node_metadata__updated_by",
  label: "Updated By",
  description: "Account that last updated the node",
};

export const METADATA_DATETIME_FILTERS: AttributeSchema[] = [
  METADATA_CREATED_AT,
  METADATA_UPDATED_AT,
];

export const METADATA_USER_FILTERS: RelationshipSchema[] = [
  METADATA_CREATED_BY,
  METADATA_UPDATED_BY,
];

export const ALL_METADATA_FILTERS: (AttributeSchema | RelationshipSchema)[] = [
  ...METADATA_DATETIME_FILTERS,
  ...METADATA_USER_FILTERS,
];
