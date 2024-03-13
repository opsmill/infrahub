import { createContext, ReactElement, ReactNode, useContext, useState } from "react";
import { ACCESS_TOKEN_KEY, ADMIN_ROLES, REFRESH_TOKEN_KEY, WRITE_ROLES } from "../config/constants";
import { fetchUrl } from "../utils/fetch";
import { CONFIG } from "../config/config";
import { toast } from "react-toastify";
import { Alert, ALERT_TYPES } from "../components/utils/alert";
import { Navigate, useLocation } from "react-router-dom";
import { configState } from "../state/atoms/config.atom";
import { useAtom } from "jotai/index";
import { parseJwt } from "../utils/common";
import { components } from "../infraops";

type PermissionsType = {
  isAdmin: boolean;
  write: boolean;
};

type AuthContextType = {
  accessToken: string | null;
  data?: any;
  isAuthenticated: boolean;
  isLoading: boolean;
  permissions?: PermissionsType;
  signIn: (data: any, callback?: () => void) => void;
  signOut: (callback?: () => void) => void;
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
    write: false,
  },
  signIn: () => {},
  signOut: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const localToken = localStorage.getItem(ACCESS_TOKEN_KEY);
  const [accessToken, setAccessToken] = useState(localToken);
  const [isLoading, setIsLoading] = useState(false);

  const signIn = async (data: any, callback?: () => void) => {
    const payload = {
      method: "POST",
      body: JSON.stringify(data),
    };

    const result: components["schemas"]["UserToken"] = await fetchUrl(
      CONFIG.AUTH_SIGN_IN_URL,
      payload
    );

    setIsLoading(false);

    if (!result?.access_token) {
      toast(<Alert type={ALERT_TYPES.ERROR} message="Invalid username and password" />, {
        toastId: "alert-error-sign-in",
      });

      return;
    }

    setAccessToken(result?.access_token);
    saveTokensInLocalStorage(result);
    if (callback) callback();
  };

  const signOut = () => {
    removeTokensInLocalStorage();
    setAccessToken(null);
  };

  const data = parseJwt(accessToken);

  const value: AuthContextType = {
    accessToken,
    data,
    isAuthenticated: !!accessToken,
    isLoading,
    permissions: {
      write: WRITE_ROLES.includes(data?.user_claims?.role),
      isAdmin: ADMIN_ROLES.includes(data?.user_claims?.role),
    },
    signIn,
    signOut,
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

  // Redirect them to the /signin page, but save the current location they were
  // trying to go to when they were redirected. This allows us to send them
  // along to that page after they log in, which is a nicer user experience
  // than dropping them off on the home page.
  return <Navigate to="/signin" state={{ from: location }} replace />;
}
