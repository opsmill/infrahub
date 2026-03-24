import type {
  BranchStatus,
  InfrahubBranch,
  InfrahubBranchType,
  InfrahubNodeMetadata,
} from "@/shared/api/graphql/generated/graphql";
import { ACCOUNT_GENERIC_OBJECT } from "@/shared/config/constants";
import type { Filter } from "@/shared/hooks/useFilters";

import type { NodeCore } from "@/entities/nodes/types";

export type InfrahubBranchResponse = {
  InfrahubBranch: InfrahubBranchType;
};

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
    __typename: "Branch",
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
    __typename: "Branch",
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

export const getNameFilterValue = (filters?: Filter[]) => {
  const nameFilter = filters?.find((f) => f.name === "any__value");
  return nameFilter?.value as string | undefined;
};

export const getStatusFilterValue = (filters?: Filter[]): BranchStatus | undefined => {
  const statusFilter = filters?.find((f) => f.name === "status__value");
  return statusFilter?.value as BranchStatus | undefined;
};

export const getCreatedByFilterValue = (filters?: Filter[]) => {
  const createdByFilter = filters?.find((f) => f.name === "node_metadata__created_by__ids");
  if (!createdByFilter?.value) return undefined;

  const relationships = createdByFilter.value as Array<{ id: string }>;
  // Return first ID since backend expects single ID, not array
  return relationships[0]?.id;
};

export const getDateFilterValue = (filters?: Filter[], fieldName?: string, condition?: string) => {
  const filter = filters?.find((f) => f.name === `${fieldName}__${condition}`);
  return filter?.value as string | undefined;
};

export const getBranchDateFilters = (filters?: Filter[]) => {
  return {
    branchedFromAfter: getDateFilterValue(filters, "branched_from", "after"),
    branchedFromBefore: getDateFilterValue(filters, "branched_from", "before"),
    createdAtAfter: getDateFilterValue(filters, "node_metadata__created_at", "after"),
    createdAtBefore: getDateFilterValue(filters, "node_metadata__created_at", "before"),
    updatedAtAfter: getDateFilterValue(filters, "node_metadata__updated_at", "after"),
    updatedAtBefore: getDateFilterValue(filters, "node_metadata__updated_at", "before"),
  };
};
