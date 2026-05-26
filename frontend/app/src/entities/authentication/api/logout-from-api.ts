import { apiClient } from "@/shared/api/rest/client";

export async function logoutFromApi(accessToken: string | null): Promise<void> {
  const { response } = await apiClient.POST("/api/auth/logout", {
    headers: accessToken ? { authorization: `Bearer ${accessToken}` } : undefined,
  });

  if (!response.ok)
    throw Object.assign(new Error("Logout failed"), { status: response.status });
}
