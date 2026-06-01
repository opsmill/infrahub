import React from "react";

import { parseJwt } from "@/shared/utils/common";

import { ACCESS_TOKEN_KEY } from "@/entities/authentication/constants";
import type { User, UserToken } from "@/entities/authentication/types";
import {
  removeTokensInLocalStorage,
  saveTokensInLocalStorage,
} from "@/entities/authentication/utils";

export type AuthContextType = {
  accessToken: string;
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
  accessToken: "",
  isAuthenticated: false,
  setToken: () => {},
  user: null,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  // Inline state instead of useLocalStorage so the cross-tab `storage`
  // listener can update React without re-writing the value back to
  // localStorage. `storage` events only fire in *other* tabs, so a
  // write-back wouldn't loop in one tab — but it would bounce a redundant
  // event to peers, doubling work on every cross-tab sync. Storage writes
  // go through `setToken`; pure state updates use `setAccessTokenState`.
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

  // Reconcile with cross-tab logout: a `storage` event signalling the access
  // token went empty in another tab means somebody signed out — drop our
  // local state so this tab follows. Covers manual devtools edits too.
  // State-only update; the originating tab already wrote to storage, so
  // re-writing here would just bounce a redundant `storage` event around.
  React.useEffect(() => {
    function handleStorage(event: StorageEvent) {
      // `localStorage.clear()` (DevTools "Clear site data", peer tab calling
      // `.clear()`) delivers `event.key === null`; that case needs to
      // reconcile too, so only skip events keyed at *other* specific keys.
      if (event.key !== null && event.key !== ACCESS_TOKEN_KEY) return;
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
