import type {
  InfrahubBranch,
  InfrahubBranchType,
  InfrahubNodeMetadata,
} from "@/shared/api/graphql/generated/types";

import type { BranchDetail, BranchListItem } from "@/entities/branches/domain/model/branch";
import type { NodeCore } from "@/entities/nodes/object/domain/model/node";
import { ACCOUNT_GENERIC_OBJECT } from "@/entities/role-manager/domain/model/account";

export type InfrahubBranchResponse = {
  InfrahubBranch: InfrahubBranchType;
};

function mapCreatedByToNodeCore(createdBy?: InfrahubNodeMetadata["created_by"]): NodeCore | null {
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
    schema_differs_from_default_branch: node.schema_differs_from_default_branch?.value,

    created_at: node_metadata?.created_at,
    updated_at: node_metadata?.updated_at,
    created_by: mapCreatedByToNodeCore(node_metadata?.created_by),
  };
}

export function mapToBranchDetail(
  node: Omit<InfrahubBranch, "is_isolated" | "graph_version">
): BranchDetail {
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
    schema_differs_from_default_branch: node.schema_differs_from_default_branch?.value,
    created_at: node.created_at,
  };
}
