import { apiClient } from "@/shared/api/rest/client";
import type { ContextParams } from "@/shared/api/types";

import type { MenuData } from "@/entities/navigation/types";

type GetMenu = (params: ContextParams) => Promise<MenuData>;

export const getMenu: GetMenu = async ({ branchName, atDate }) => {
  const { data, error } = await apiClient.GET("/api/menu", {
    params: {
      query: {
        branch: branchName,
        date: atDate,
      },
    },
  });

  if (error) throw error;

  return data as MenuData;
};
