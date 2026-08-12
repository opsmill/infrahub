import { apiClient } from "@/shared/api/rest/client";
import type { components } from "@/shared/api/rest/types.generated";

export type LoginWithCredentialsFromApiParams = {
  username: string;
  password: string;
};

export async function loginWithCredentialsFromApi(
  params: LoginWithCredentialsFromApiParams
): Promise<components["schemas"]["UserToken"]> {
  const { data, error, response } = await apiClient.POST("/api/auth/login", { body: params });

  if (error)
    throw Object.assign(new Error("Login failed"), { status: response.status, body: error });

  return data;
}
