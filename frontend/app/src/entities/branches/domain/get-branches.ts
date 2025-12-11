import type { Branch } from "@/shared/api/graphql/generated/graphql";
import { store } from "@/shared/stores";

import { getBranchesFromApi } from "@/entities/branches/api/get-branches-from-api";
import {
  type InfrahubBranchResponse,
  mapInfrahubBranchNodeToBranch,
} from "@/entities/branches/domain/branch-response.types";
import { branchesState } from "@/entities/branches/stores";

export type GetBranches = () => Promise<Array<Branch>>;

export const getBranches: GetBranches = async () => {
  const { data, errors } = await getBranchesFromApi();

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const response = data as InfrahubBranchResponse;
  const branches: Branch[] =
    response?.InfrahubBranch?.edges.map(({ node }) => mapInfrahubBranchNodeToBranch(node)) ?? [];

  store.set(branchesState, branches);

  return branches;
};
