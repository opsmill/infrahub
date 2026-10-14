import { getRepositorySyncCountsFromApi } from "@/entities/repository/api/get-repository-sync-counts-from-api";

export type RepositorySyncHealth = "none" | "failing" | "in-sync";

export type GetRepositorySyncHealth = (branch: string) => Promise<RepositorySyncHealth>;

export const getRepositorySyncHealth: GetRepositorySyncHealth = async (branch: string) => {
  // `atDate: null` reports current state, whatever time frame the page is showing.
  const { data, errors } = await getRepositorySyncCountsFromApi({
    branchName: branch,
    atDate: null,
  });

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  if (data.total.count === 0) return "none";

  return data.failing.count > 0 ? "failing" : "in-sync";
};
