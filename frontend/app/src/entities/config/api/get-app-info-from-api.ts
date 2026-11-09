import { apiClient } from "@/shared/api/rest/client";

export function getAppInfoFromApi() {
  return apiClient.GET("/api/info");
}
