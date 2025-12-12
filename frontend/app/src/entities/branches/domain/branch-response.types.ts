import type {
  Branch,
  InfrahubBranch,
  InfrahubBranchType,
} from "@/shared/api/graphql/generated/graphql";

export type InfrahubBranchResponse = {
  InfrahubBranch?: InfrahubBranchType;
};

export function mapInfrahubBranchNodeToBranch(node: InfrahubBranch): Branch {
  return {
    id: node.id,
    name: node.name.value,
    description: node.description?.value,
    origin_branch: node.origin_branch?.value,
    branched_from: node.branched_from?.value,
    created_at: node.created_at,
    status: node.status?.value,
    sync_with_git: node.sync_with_git?.value,
    is_default: node.is_default?.value,
    has_schema_changes: node.has_schema_changes?.value,
  };
}
