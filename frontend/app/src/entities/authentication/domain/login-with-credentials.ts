import { apiClient } from "@/shared/api/rest/client";

import type { UserToken } from "@/entities/authentication/types";
import { saveTokensInLocalStorage } from "@/entities/authentication/utils";

export type LoginWithCredentialsParams = {
  username: string;
  password: string;
};

export type LoginWithCredentials = (params: LoginWithCredentialsParams) => Promise<UserToken>;

export const loginWithCredentials: LoginWithCredentials = async (params) => {
  const { data, error } = await apiClient.POST("/api/auth/login", {
    body: params,
  });

  if (error) throw error;

  saveTokensInLocalStorage(data);
  return data;
};
