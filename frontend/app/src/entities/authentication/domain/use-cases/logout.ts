import { logoutFromApi } from "@/entities/authentication/api/logout-from-api";
import { removeTokensInLocalStorage } from "@/entities/authentication/api/token-storage";
import { ACCESS_TOKEN_KEY } from "@/entities/authentication/constants";

export type Logout = () => Promise<void>;

export const logout: Logout = async () => {
  const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
  await logoutFromApi(accessToken);
  removeTokensInLocalStorage();
};
