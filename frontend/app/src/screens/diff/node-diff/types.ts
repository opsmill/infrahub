export const DIFF_STATUS = {
  ADDED: "ADDED",
  REMOVED: "REMOVED",
  UPDATED: "UPDATED",
  CONFLICT: "CONFLICT",
  UNCHANGED: "UNCHANGED",
} as const;

export type DiffStatus = (typeof DIFF_STATUS)[keyof typeof DIFF_STATUS];

export type DiffConflict = {
  base_branch_action: DiffStatus;
  base_branch_changed_at: string;
  base_branch_value: any;
  diff_branch_action: DiffStatus;
  diff_branch_changed_at: "2024-08-21T19:06:12.429813+00:00";
  diff_branch_value: any;
  uuid: string;
};

export type DiffProperty = {
  last_changed_at: string;
  conflict: DiffConflict | null;
  new_value: any;
  previous_value: any;
  property_type:
    | "HAS_VALUE"
    | "HAS_OWNER"
    | "HAS_SOURCE"
    | "IS_VISIBLE"
    | "IS_PROTECTED"
    | "IS_RELATED";
  path_identifier: string | null;
  status: DiffStatus;
};

export type DiffAttribute = {
  uuid: string;
  name: string;
  properties: Array<DiffProperty>;
  path_identifier: string | null;
  contains_conflict: boolean;
};

export type DiffRelationshipElement = {
  peer_id: string;
  peer_label: string;
  properties: Array<DiffProperty>;
  status: DiffStatus;
  path_identifier: string;
  conflict: DiffConflict | null;
  contains_conflict: boolean;
};

export type DiffRelationship = {
  uuid: string;
  name: string;
  label: string;
  elements: Array<DiffRelationshipElement>;
  path_identifier: string | null;
  contains_conflict: boolean;
};

export type DiffNode = {
  attributes: Array<DiffAttribute>;
  conflict: DiffConflict | null;
  contains_conflict: boolean;
  kind: string;
  label: string;
  last_changed_at?: string;
  num_added?: number;
  num_conflicts?: number;
  num_removed?: number;
  num_updated?: number;
  parent?: {
    kind?: string;
    relationship_name?: string;
    uuid: string;
  } | null;
  path_identifier: string;
  relationships: Array<DiffRelationship>;
  status: DiffStatus;
  uuid: string;
};
