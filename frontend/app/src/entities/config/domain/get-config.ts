import { getConfigFromApi } from "@/entities/config/api/get-config-from-api";
import type { Config } from "@/entities/config/domain/model/config";

export type GetConfig = () => Promise<Config>;

export const getConfig: GetConfig = async () => {
  const { data, error } = await getConfigFromApi();

  if (error) throw error;

  return data;
};
