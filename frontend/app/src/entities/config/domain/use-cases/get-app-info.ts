import { getAppInfoFromApi } from "@/entities/config/api/get-app-info-from-api";

export const getAppInfo = async () => {
  const { data, error } = await getAppInfoFromApi();

  if (error) throw error;

  return data;
};
