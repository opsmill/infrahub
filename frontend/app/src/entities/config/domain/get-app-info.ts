import { apiClient } from "@/shared/api/rest/client";

export const getAppInfo = async () => {
  const { data, error } = await apiClient.GET("/api/info");

  if (error) throw error;

  return data;
};
