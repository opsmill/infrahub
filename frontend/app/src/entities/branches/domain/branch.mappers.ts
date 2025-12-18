import type {
  InfrahubBranch,
  InfrahubBranchType,
  InfrahubNodeMetadata,
} from "@/shared/api/graphql/generated/graphql";
import { ACCOUNT_GENERIC_OBJECT } from "@/shared/config/constants";

import type { NodeCore } from "@/entities/nodes/types";

export type InfrahubBranchResponse = {
  InfrahubBranch: InfrahubBranchType;
};

// Base fields present in both list and detail views
interface BranchBase {
  id: string;
  name: string;
  description?: string | null;
  branched_from?: string | null;
  status: string;
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

function mapCreatedByToNodeCore(createdBy: InfrahubNodeMetadata["created_by"]): NodeCore | null {
  if (!createdBy?.id) return null;

  return {
    id: createdBy.id,
    display_label: createdBy.display_label,
    hfid: createdBy.hfid,
    __typename: ACCOUNT_GENERIC_OBJECT,
  };
}

interface MapToBranchListItemParams {
  node: InfrahubBranch;
  node_metadata?: InfrahubNodeMetadata;
}

export function mapToBranchListItem({
  node,
  node_metadata,
}: MapToBranchListItemParams): BranchListItem {
  return {
    id: node.id,
    name: node.name.value,
    description: node.description?.value,
    branched_from: node.branched_from?.value,
    status: node.status.value,
    sync_with_git: node.sync_with_git?.value,
    is_default: node.is_default?.value,
    has_schema_changes: node.has_schema_changes?.value,

    created_at: node_metadata?.created_at,
    updated_at: node_metadata?.updated_at,
    created_by: mapCreatedByToNodeCore(node_metadata?.created_by),
  };
}

export function mapToBranchDetail(node: InfrahubBranch): BranchDetail {
  return {
    id: node.id,
    name: node.name.value,
    description: node.description?.value,
    origin_branch: node.origin_branch?.value,
    branched_from: node.branched_from?.value,
    status: node.status.value,
    sync_with_git: node.sync_with_git?.value,
    is_default: node.is_default?.value,
    has_schema_changes: node.has_schema_changes?.value,
    created_at: node.created_at,
  };
}
