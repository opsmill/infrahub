import type { BranchListItem } from "@/entities/branches/domain/branch.mappers";

export const generateBranch = (overrides?: Partial<BranchListItem>): BranchListItem => {
  return {
    id: "1810645c-7f11-807a-30f9-c511d481b315",
    name: "test-branch",
    description: "test-branch's description",
    branched_from: "2024-12-12T09:36:44.968813Z",
    created_at: "2024-12-12T09:36:44.968848Z",
    sync_with_git: false,
    is_default: false,
    has_schema_changes: false,
    status: "OPEN",
    __typename: "Branch",
    ...overrides,
  };
};
