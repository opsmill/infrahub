import { apiClient } from "@/shared/api/rest/client";

import type { ConfigAPI } from "@/entities/config/types";

export type GetConfig = () => Promise<ConfigAPI>;

export const getConfig: GetConfig = async () => {
  const { data, error } = await apiClient.GET("/api/config");

  if (error) throw error;

  return data;
};
