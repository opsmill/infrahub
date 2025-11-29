import React from "react";

import { ACCESS_TOKEN_KEY } from "@/shared/config/localStorage";
import { useLocalStorage } from "@/shared/hooks/useLocalStorage";
import { parseJwt } from "@/shared/utils/common";

import type { User, UserToken } from "@/entities/authentication/types";
import {
  removeTokensInLocalStorage,
  saveTokensInLocalStorage,
} from "@/entities/authentication/utils";

export type AuthContextType = {
  accessToken: string | null;
  data?: any;
  isAuthenticated: boolean;
  setToken: (token: UserToken | null) => void;
  user: User | null;
};

export const AuthContext = React.createContext<AuthContextType>({
  accessToken: null,
  isAuthenticated: false,
  data: undefined,
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

  const data = parseJwt(accessToken);

  const value: AuthContextType = {
    accessToken,
    data,
    isAuthenticated: !!accessToken,
    setToken,
    user: data?.sub ? { id: data?.sub } : null,
  };

  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth() {
  const context = React.use(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used within an AuthContext.");
  }

  return context;
}
