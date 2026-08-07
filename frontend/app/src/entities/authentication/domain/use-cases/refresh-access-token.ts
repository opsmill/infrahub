import {
  type RefreshAccessTokenFromApiResult,
  refreshAccessTokenFromApi,
} from "@/entities/authentication/api/refresh-access-token-from-api";
import {
  getRefreshToken,
  saveTokensInLocalStorage,
} from "@/entities/authentication/api/token-storage";

export type RefreshAccessToken = () => Promise<RefreshAccessTokenFromApiResult>;

export const refreshAccessToken: RefreshAccessToken = async () => {
  const refreshToken = getRefreshToken();

  if (!refreshToken) {
    throw new Error("Refresh token not found");
  }

  const data = await refreshAccessTokenFromApi(refreshToken);
  saveTokensInLocalStorage(data);
  return data;
};
