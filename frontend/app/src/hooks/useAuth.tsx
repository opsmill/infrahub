import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { CONFIG } from "@/config/config";
import { ADMIN_ROLES, REFRESH_TOKEN_KEY } from "@/config/constants";
import { ACCESS_TOKEN_KEY } from "@/config/localStorage";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { components } from "@/infraops";
import { configState } from "@/state/atoms/config.atom";
import { parseJwt } from "@/utils/common";
import { fetchUrl } from "@/utils/fetch";
import { useAtom } from "jotai/index";
import { ReactElement, ReactNode, createContext, useContext, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { toast } from "react-toastify";

type PermissionsType = {
  isAdmin: boolean;
};

type User = {
  id: string;
};

type UserToken = {
  access_token: string;
  refresh_token: string;
};

export type AuthContextType = {
  accessToken: string | null;
  data?: any;
  isAuthenticated: boolean;
  isLoading: boolean;
  permissions?: PermissionsType;
  login: (data: { username: string; password: string }, callback?: () => void) => Promise<void>;
  signOut: (callback?: () => void) => void;
  setToken: (token: UserToken) => void;
  user: User | null;
};

export const saveTokensInLocalStorage = (result: any) => {
  if (result?.access_token) {
    localStorage.setItem(ACCESS_TOKEN_KEY, result?.access_token);
  }

  if (result?.refresh_token) {
    localStorage.setItem(REFRESH_TOKEN_KEY, result?.refresh_token);
  }
};

export const removeTokensInLocalStorage = () => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
};

export const getNewToken = async () => {
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);

  if (!refreshToken) {
    return;
  }

  const payload = {
    method: "POST",
    headers: {
      authorization: `Bearer ${refreshToken}`,
    },
  };

  const result: components["schemas"]["AccessTokenResponse"] = await fetchUrl(
    CONFIG.AUTH_REFRESH_TOKEN_URL,
    payload
  );

  if (!result?.access_token) {
    removeTokensInLocalStorage();
    window.location.reload();
    return;
  }

  saveTokensInLocalStorage(result);

  return result;
};

export const AuthContext = createContext<AuthContextType>({
  accessToken: null,
  isAuthenticated: false,
  isLoading: false,
  data: undefined,
  permissions: {
    isAdmin: false,
  },
  login: async () => {},
  signOut: () => {},
  setToken: () => {},
  user: null,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const localToken = localStorage.getItem(ACCESS_TOKEN_KEY);
  const [accessToken, setAccessToken] = useState(localToken);
  const [isLoading, setIsLoading] = useState(false);

  const setToken = (token: UserToken) => {
    setAccessToken(token.access_token);
    saveTokensInLocalStorage(token);
  };

  const signIn = async (data: { username: string; password: string }, callback?: () => void) => {
    const payload = {
      method: "POST",
      body: JSON.stringify(data),
    };

    const result: components["schemas"]["UserToken"] = await fetchUrl(
      CONFIG.AUTH_LOGIN_URL,
      payload
    );

    setIsLoading(false);

    if (!result?.access_token) {
      toast(<Alert type={ALERT_TYPES.ERROR} message="Invalid username and password" />, {
        toastId: "alert-error-sign-in",
      });

      return;
    }

    setToken(result);
    if (callback) callback();
  };

  const signOut = () => {
    removeTokensInLocalStorage();
    setAccessToken(null);
    graphqlClient.refetchQueries({ include: "active" });
  };

  const data = parseJwt(accessToken);

  const value: AuthContextType = {
    accessToken,
    data,
    isAuthenticated: !!accessToken,
    isLoading,
    permissions: {
      isAdmin: ADMIN_ROLES.includes(data?.user_claims?.role),
    },
    login: signIn,
    signOut,
    setToken,
    user: data?.sub ? { id: data?.sub } : null,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}

export function RequireAuth({ children }: { children: ReactElement }) {
  const [config] = useAtom(configState);
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  if (isAuthenticated || config?.main?.allow_anonymous_access) return children;

  // Redirect them to the /login page, but save the current location they were
  // trying to go to when they were redirected. This allows us to send them
  // along to that page after they log in, which is a nicer user experience
  // than dropping them off on the home page.
  return <Navigate to="/login" state={{ from: location }} replace />;
}
