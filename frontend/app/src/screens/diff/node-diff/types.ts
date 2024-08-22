type Status = "ADDED" | "UPDATED" | "REMOVED";

export type DiffPropertyConflict = {
  base_branch_action: Status;
  base_branch_changed_at: string;
  base_branch_value: any;
  diff_branch_action: Status;
  diff_branch_changed_at: "2024-08-21T19:06:12.429813+00:00";
  diff_branch_value: any;
  uuid: string;
};

export type DiffProperty = {
  last_changed_at: string;
  conflict: DiffPropertyConflict | null;
  new_value: any;
  previous_value: any;
  property_type: "HAS_VALUE" | "HAS_OWNER" | "HAS_SOURCE" | "IS_VISIBLE" | "IS_PROTECTED";
  path_identifier: string | null;
  status: Status;
};

export type DiffAttribute = {
  name: string;
  properties: Array<DiffProperty>;
  path_identifier: string | null;
  contains_conflict: boolean;
};

export type DiffRelationship = {
  name: string;
  label: string;
  elements: Array<DiffProperty & { peer_label: string }>;
  path_identifier: string | null;
  contains_conflict: boolean;
};
