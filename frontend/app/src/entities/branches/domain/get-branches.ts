import type { Branch } from "@/shared/api/graphql/generated/graphql";
import { store } from "@/shared/stores";

import { getBranchesFromApi } from "@/entities/branches/api/get-branches-from-api";
import { branchesState } from "@/entities/branches/stores";

// Type for the new InfrahubBranch query response structure
// TODO: Remove once codegen is regenerated with the new schema
type InfrahubBranchNode = {
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

type InfrahubBranchResponse = {
  InfrahubBranch?: {
    edges: Array<{ node: InfrahubBranchNode }>;
  };
};

export type GetBranches = () => Promise<Array<Branch>>;

export const getBranches: GetBranches = async () => {
  const { data, errors } = await getBranchesFromApi();

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const response = data as InfrahubBranchResponse;
  const branches: Branch[] =
    response?.InfrahubBranch?.edges.map(({ node }) => ({
      id: node.id,
      name: node.name.value,
      description: node.description?.value,
      origin_branch: node.origin_branch?.value,
      branched_from: node.branched_from?.value,
      created_at: node.created_at,
      sync_with_git: node.sync_with_git?.value,
      is_default: node.is_default?.value,
      has_schema_changes: node.has_schema_changes?.value,
    })) ?? [];

  store.set(branchesState, branches);

  return branches;
};
