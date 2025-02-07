import { getBranchesFromApi } from "@/entities/branches/api/get-branches-from-api";
import { branchesState } from "@/entities/branches/stores";
import { Branch } from "@/shared/api/graphql/generated/graphql";
import { store } from "@/shared/stores";

export type GetBranches = () => Promise<Array<Branch>>;

export const getBranches: GetBranches = async () => {
  const { data, error } = await getBranchesFromApi();

  if (error) throw error;

  const branches = data?.Branch ?? [];
  store.set(branchesState, branches);

  return branches;
};
