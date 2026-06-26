import { apiClient } from "@/shared/api/rest/client";
import type { components } from "@/shared/api/rest/types.generated";

export type RefreshAccessTokenFromApiResult = components["schemas"]["AccessTokenResponse"];

export async function refreshAccessTokenFromApi(
  refreshToken: string
): Promise<RefreshAccessTokenFromApiResult> {
  const { data, error } = await apiClient.POST("/api/auth/refresh", {
    headers: {
      authorization: `Bearer ${refreshToken}`,
    },
  });

  if (error) throw error;

  return data;
}
