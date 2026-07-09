import { apiClient } from "@/shared/api/rest/client";

export function getConfigFromApi() {
  return apiClient.GET("/api/config");
}
