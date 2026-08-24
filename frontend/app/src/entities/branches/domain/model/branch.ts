import type { BranchStatus } from "@/shared/api/graphql/generated/types";

import type { NodeCore } from "@/entities/nodes/object/domain/model/node";

// Explains the sync_with_git flag: it controls the Infrahub -> Git direction only,
// and is not an indicator of whether a branch originated from Git.
export const SYNC_WITH_GIT_DESCRIPTION =
  "Whether branches created in Infrahub are also created in connected read/write Git repositories and merged back to Git when a proposed change is merged. This does not indicate whether the branch originated from Git.";

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

// List view - includes node_metadata fields and schema_differs_from_default_branch
export interface BranchListItem extends BranchBase {
  schema_differs_from_default_branch?: boolean | null;
  created_at?: string | null;
  updated_at?: string | null;
  created_by?: NodeCore | null;
}

// Detail view - includes origin_branch, schema_differs_from_default_branch, created_at (from node)
export interface BranchDetail extends BranchBase {
  origin_branch?: string | null;
  schema_differs_from_default_branch?: boolean | null;
  created_at?: string | null;
}
