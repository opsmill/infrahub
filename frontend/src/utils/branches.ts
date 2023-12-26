import { Branch } from "../generated/graphql";

export const findSelectedBranch = (branches: Branch[], branchName?: string | null) => {
  const filter = branchName ? (b: Branch) => branchName === b.name : (b: Branch) => b.is_default;

  return branches.find(filter) ?? null;
};
