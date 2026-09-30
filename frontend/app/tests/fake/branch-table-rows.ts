import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import type { BranchTableRow } from "@/entities/branches/domain/model/branch-table-row";
import type { BranchRepository } from "@/entities/repository/domain/model/branch-repository";

import { generateBranch } from "./branch";
import { generateBranchRepository } from "./branch-repositories";

export const FULL_COMMIT_HASH = "8f3c2a1b9d4e5f60718293a4b5c6d7e8f9012345";

export const generateBranchTableRow = (
  overrides: { branch?: Partial<BranchListItem>; repository?: Partial<BranchRepository> } = {}
): BranchTableRow => {
  const branch = generateBranch(overrides.branch);
  return {
    id: branch.id,
    branch,
    state: "ok",
    repository: generateBranchRepository({ commit: FULL_COMMIT_HASH, ...overrides.repository }),
  };
};
