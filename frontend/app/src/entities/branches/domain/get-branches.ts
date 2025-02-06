import { getBranchesFromApi } from "@/entities/branches/api/get-branches-from-api";
import { branchesState, currentBranchAtom } from "@/entities/branches/stores";
import { findSelectedBranch } from "@/entities/branches/utils";
import { Branch } from "@/shared/api/graphql/generated/graphql";
import { store } from "@/shared/stores";

export type GetBranches = () => Promise<Array<Branch>>;

export const getBranches: GetBranches = async () => {
  const { data, error } = await getBranchesFromApi();

  if (error) throw error;

  const branches = data?.Branch ?? [];

  const params = new URLSearchParams(window.location.search);
  const currentBranch = findSelectedBranch(branches, params.get("branch"));
  store.set(branchesState, branches);
  store.set(currentBranchAtom, currentBranch);

  return branches;
};
