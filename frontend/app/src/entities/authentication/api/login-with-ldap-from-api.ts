import { apiClient } from "@/shared/api/rest/client";
import type { components } from "@/shared/api/rest/types.generated";

export type LoginWithLdapFromApiParams = {
  username: string;
  password: string;
};

export async function loginWithLdapFromApi(
  params: LoginWithLdapFromApiParams
): Promise<components["schemas"]["UserToken"]> {
  const { data, error, response } = await apiClient.POST("/api/auth/ldap/login", { body: params });

  if (error)
    throw Object.assign(new Error("LDAP login failed"), { status: response.status, body: error });

  return data;
}
