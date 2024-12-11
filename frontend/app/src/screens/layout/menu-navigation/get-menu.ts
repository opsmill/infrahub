import { apiClient } from "@/api/client";
import { DEFAULT_BRANCH_NAME } from "@/config/constants";
import { MenuData } from "@/screens/layout/menu-navigation/types";
import { store } from "@/state";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { queryOptions } from "@tanstack/react-query";

type GetMenu = ({ branchName }: { branchName: string }) => Promise<MenuData>;

const getMenu: GetMenu = async ({ branchName }) => {
  const { data, error } = await apiClient.GET("/api/menu", {
    params: {
      query: {
        branch: branchName,
      },
    },
  });

  if (error) throw error;

  return data as MenuData;
};

export function menuQueryOptions() {
  const currentBranch = store.get(currentBranchAtom);

  return queryOptions({
    queryKey: ["menu", currentBranch?.name],
    queryFn: () => getMenu({ branchName: currentBranch?.name ?? DEFAULT_BRANCH_NAME }),
    enabled: !!currentBranch,
  });
}
