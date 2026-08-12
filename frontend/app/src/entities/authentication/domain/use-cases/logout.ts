import { logoutFromApi } from "@/entities/authentication/api/logout-from-api";
import {
  getAccessToken,
  removeTokensInLocalStorage,
} from "@/entities/authentication/api/token-storage";

export type Logout = () => Promise<void>;

export const logout: Logout = async () => {
  const accessToken = getAccessToken();
  await logoutFromApi(accessToken);
  removeTokensInLocalStorage();
};
