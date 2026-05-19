import { apiClient } from "@/shared/api/rest/client";

import type { UserToken } from "@/entities/authentication/types";

export type LoginWithLdapParams = {
  username: string;
  password: string;
};

export type LoginWithLdap = (params: LoginWithLdapParams) => Promise<UserToken>;

export const loginWithLdap: LoginWithLdap = async (params) => {
  const { data, error, response } = await apiClient.POST("/api/auth/ldap/login", {
    body: params,
  });

  if (error)
    throw Object.assign(new Error("LDAP login failed"), {
      status: response.status,
      body: error,
    });

  return data;
};
