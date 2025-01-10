import { DEFAULT_BRANCH_NAME } from "@/config/constants";
import { currentBranchAtom } from "@/entities/branches/branches.atom";
import { apiClient } from "@/shared/api/rest/client";
import { MenuData } from "@/shared/components/layout/menu-navigation/types";
import { store } from "@/shared/stores";
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
