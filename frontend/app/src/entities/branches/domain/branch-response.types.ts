import type { Branch } from "@/shared/api/graphql/generated/graphql";

// Type for the new InfrahubBranch query response structure
// TODO: Remove once codegen is regenerated with the new schema
export type InfrahubBranchNode = {
  id: string;
  name: { value: string };
  description?: { value?: string | null } | null;
  origin_branch?: { value?: string | null } | null;
  branched_from?: { value?: string | null } | null;
  status?: { value?: string | null } | null;
  created_at?: string | null;
  sync_with_git?: { value?: boolean | null } | null;
  is_default?: { value?: boolean | null } | null;
  has_schema_changes?: { value?: boolean | null } | null;
};

export type InfrahubBranchResponse = {
  InfrahubBranch?: {
    edges: Array<{ node: InfrahubBranchNode }>;
  };
};

export function mapInfrahubBranchNodeToBranch(node: InfrahubBranchNode): Branch {
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
