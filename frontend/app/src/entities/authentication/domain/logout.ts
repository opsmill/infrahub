import { apiClient } from "@/shared/api/rest/client";

import { ACCESS_TOKEN_KEY } from "@/entities/authentication/constants";
import { removeTokensInLocalStorage } from "@/entities/authentication/utils";

export type Logout = () => Promise<void>;

export const logout: Logout = async () => {
  const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);

  await apiClient.POST("/api/auth/logout", {
    headers: {
      authorization: `Bearer ${accessToken}`,
    },
  });
  removeTokensInLocalStorage();
};
