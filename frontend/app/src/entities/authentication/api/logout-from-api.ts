import { apiClient } from "@/shared/api/rest/client";

export async function logoutFromApi(accessToken: string | null): Promise<void> {
  await apiClient.POST("/api/auth/logout", {
    headers: {
      authorization: `Bearer ${accessToken}`,
    },
  });
}
