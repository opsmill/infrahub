import type { BranchStatus } from "@/shared/api/graphql/generated/types";

import type { NodeCore } from "@/entities/nodes/object/domain/model/node";

export const DEFAULT_BRANCH_NAME = "main";

// Base fields present in both list and detail views
interface BranchBase {
  id: string;
  __typename: "Branch";
  name: string;
  description?: string | null;
  branched_from?: string | null;
  status: BranchStatus;
  sync_with_git?: boolean | null;
  is_default?: boolean | null;
}

// List view - includes node_metadata fields and has_schema_changes
export interface BranchListItem extends BranchBase {
  has_schema_changes?: boolean | null;
  created_at?: string | null;
  updated_at?: string | null;
  created_by?: NodeCore | null;
}

// Detail view - includes origin_branch, has_schema_changes, created_at (from node)
export interface BranchDetail extends BranchBase {
  origin_branch?: string | null;
  has_schema_changes?: boolean | null;
  created_at?: string | null;
}
