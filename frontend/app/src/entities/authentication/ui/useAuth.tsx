import React from "react";

import { useLocalStorage } from "@/shared/hooks/useLocalStorage";
import { parseJwt } from "@/shared/utils/common";

import { ACCESS_TOKEN_KEY } from "@/entities/authentication/constants";
import type { User, UserToken } from "@/entities/authentication/types";
import {
  removeTokensInLocalStorage,
  saveTokensInLocalStorage,
} from "@/entities/authentication/utils";

export type AuthContextType = {
  accessToken: string | null;
  isAuthenticated: boolean;
  setToken: (token: UserToken | null) => void;
  user: User | null;
};

function extractUser(payload: unknown): User | null {
  if (
    payload &&
    typeof payload === "object" &&
    "sub" in payload &&
    typeof payload.sub === "string"
  ) {
    return { id: payload.sub };
  }
  return null;
}

export const AuthContext = React.createContext<AuthContextType>({
  accessToken: null,
  isAuthenticated: false,
  setToken: () => {},
  user: null,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [accessToken, setAccessToken] = useLocalStorage(ACCESS_TOKEN_KEY);

  const setToken: AuthContextType["setToken"] = (token) => {
    if (token) {
      setAccessToken(token.access_token);
      saveTokensInLocalStorage(token);
    } else {
      setAccessToken("");
      removeTokensInLocalStorage();
    }
  };

  const value: AuthContextType = {
    accessToken,
    isAuthenticated: !!accessToken,
    setToken,
    user: extractUser(parseJwt(accessToken)),
  };

  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth() {
  return React.use(AuthContext);
}
