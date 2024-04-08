import { Branch } from "../generated/graphql";

export const findSelectedBranch = (branches: Branch[], branchName?: string | null) => {
  const filter = branchName ? (b: Branch) => branchName === b.name : (b: Branch) => b.is_default;

  return branches.find(filter) ?? null;
};

export const branchesToSelectOptions = (branches: Branch[]) =>
  branches
    .map((branch) => ({
      id: branch.name,
      name: branch.name,
      sync_with_git: branch.sync_with_git,
      is_default: branch.is_default,
      is_isolated: branch.is_isolated,
      has_schema_changes: branch.has_schema_changes,
      created_at: branch.created_at,
    }))
    .sort((branch1, branch2) => {
      if (branch1.name === "main") {
        return -1;
      }

      if (branch2.name === "main") {
        return 1;
      }

      if (branch2.name === "main") {
        return -1;
      }

      if (branch1.name > branch2.name) {
        return 1;
      }

      return -1;
    });
