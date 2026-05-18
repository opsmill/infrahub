import { apiClient } from "@/shared/api/rest/client";

import type { UserToken } from "@/entities/authentication/types";

export type LoginWithCredentialsParams = {
  username: string;
  password: string;
};

export type LoginWithCredentials = (params: LoginWithCredentialsParams) => Promise<UserToken>;

export const loginWithCredentials: LoginWithCredentials = async (params) => {
  const { data, error, response } = await apiClient.POST("/api/auth/login", {
    body: params,
  });

  if (error)
    throw Object.assign(new Error("Login failed"), { status: response.status, body: error });

  return data;
};
