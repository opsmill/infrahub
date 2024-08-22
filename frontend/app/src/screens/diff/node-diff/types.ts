type Status = "ADDED" | "UPDATED" | "REMOVED" | "UNCHANGED";

export type DiffConflict = {
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
  status: Status;
};

export type DiffAttribute = {
  name: string;
  properties: Array<DiffProperty>;
  path_identifier: string | null;
  contains_conflict: boolean;
};

export type DiffRelationshipElement = {
  peer_id: string;
  peer_label: string;
  properties: Array<DiffProperty>;
  status: Status;
  path_identifier: string;
  conflict: DiffConflict | null;
};

export type DiffRelationship = {
  name: string;
  label: string;
  elements: Array<DiffRelationshipElement>;
  path_identifier: string | null;
  contains_conflict: boolean;
};
