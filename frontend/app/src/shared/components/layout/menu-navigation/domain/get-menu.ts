import { apiClient } from "@/shared/api/rest/client";
import { MenuData } from "@/shared/components/layout/menu-navigation/types";

type GetMenu = ({ branchName }: { branchName: string }) => Promise<MenuData>;

export const getMenu: GetMenu = async ({ branchName }) => {
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
