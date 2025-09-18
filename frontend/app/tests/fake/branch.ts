import type { Branch } from "@/shared/api/graphql/generated/graphql";

export const generateBranch = (overrides?: Partial<Branch>): Branch => {
  return {
    id: "1810645c-7f11-807a-30f9-c511d481b315",
    name: "test-branch",
    description: "test-branch's description",
    origin_branch: "main",
    branched_from: "2024-12-12T09:36:44.968813Z",
    created_at: "2024-12-12T09:36:44.968848Z",
    sync_with_git: false,
    is_default: false,
    has_schema_changes: false,
    __typename: "Branch",
    ...overrides,
  };
};
