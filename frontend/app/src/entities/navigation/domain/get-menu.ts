import type { ContextParams } from "@/shared/api/types";

import { getMenuFromApi } from "@/entities/navigation/api/get-menu-from-api";
import type { MenuData } from "@/entities/navigation/domain/model/menu";

type GetMenu = (params: ContextParams) => Promise<MenuData>;

export const getMenu: GetMenu = async (params) => {
  const { data, error } = await getMenuFromApi(params);

  if (error) throw error;

  return data as MenuData;
};
