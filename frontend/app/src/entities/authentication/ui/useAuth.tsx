import React from "react";

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
  // Inline state instead of useLocalStorage so the cross-tab `storage`
  // listener can update React without re-writing the value back to
  // localStorage (which would cascade `storage` events between tabs and
  // loop forever). Storage writes go through `setToken` / `logoutLocally`;
  // pure state updates use `setAccessTokenState` directly.
  const [accessToken, setAccessTokenState] = React.useState<string>(
    () => localStorage.getItem(ACCESS_TOKEN_KEY) ?? ""
  );

  const setToken: AuthContextType["setToken"] = (token) => {
    if (token) {
      setAccessTokenState(token.access_token);
      saveTokensInLocalStorage(token);
    } else {
      setAccessTokenState("");
      removeTokensInLocalStorage();
    }
  };

  // Reconcile with cross-tab logout: a `storage` event with the access-token
  // key going empty in another tab means somebody signed out — drop our
  // local state so this tab follows. Covers manual devtools edits too.
  // State-only update; the originating tab already wrote to storage, so
  // re-writing here would just bounce a redundant `storage` event around.
  React.useEffect(() => {
    function handleStorage(event: StorageEvent) {
      if (event.key !== ACCESS_TOKEN_KEY) return;
      // Re-read rather than trusting event.newValue — `localStorage.clear()`
      // delivers `newValue: null`, and we want to match the post-clear state.
      const current = localStorage.getItem(ACCESS_TOKEN_KEY) ?? "";
      setAccessTokenState(current);
    }
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

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
