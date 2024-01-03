import { useAtom } from "jotai";
import { createContext, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../components/alert";
import { CONFIG } from "../config/config";
import { ACCESS_TOKEN_KEY, ADMIN_ROLES, REFRESH_TOKEN_KEY, WRITE_ROLES } from "../config/constants";
import SignIn from "../screens/sign-in/sign-in";
import { configState } from "../state/atoms/config.atom";
import { parseJwt } from "../utils/common";
import { fetchUrl } from "../utils/fetch";
import { components } from "../infraops";

type tPermissions = {
  write?: boolean;
  read?: boolean;
};

type tAuthContext = {
  accessToken?: string;
  displaySignIn?: Function;
  signOut?: Function;
  permissions?: tPermissions;
  data?: any;
};

// Export auth context
export const AuthContext = createContext({} as tAuthContext);

export const setTokens = (result: any) => {
  if (result?.access_token) {
    localStorage.setItem(ACCESS_TOKEN_KEY, result?.access_token);
  }

  if (result?.refresh_token) {
    localStorage.setItem(REFRESH_TOKEN_KEY, result?.refresh_token);
  }
};

export const removeTokens = () => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
};

export const signOut = () => {
  removeTokens();
  window.location.reload();
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
    return signOut();
  }

  setTokens(result);

  return result;
};

// Add auth data in compo
export const withAuth = (AppComponent: any) => (props: any) => {
  const [config] = useAtom(configState);

  const localToken = localStorage.getItem(ACCESS_TOKEN_KEY);

  const isSigning = window.location.pathname === "/signin";

  const [isLoading, setIsLoading] = useState(false);
  const [displaySignIn, setDisplaySignin] = useState(isSigning);
  const [accessToken, setAccessToken] = useState(localToken);
  const navigate = useNavigate();

  const signOut = async () => {
    await fetchUrl(CONFIG.LOGOUT_URL, {
      method: "POST",
      headers: {
        authorization: `Bearer ${accessToken}`,
      },
    });
    removeTokens();
    setAccessToken("");
  };

  const signIn = async (data: any) => {
    const payload = {
      method: "POST",
      body: JSON.stringify(data),
    };

    const result = await fetchUrl(CONFIG.AUTH_SIGN_IN_URL, payload);

    setIsLoading(false);

    if (!result?.access_token) {
      toast(<Alert type={ALERT_TYPES.ERROR} message="Invalid username and password" />);

      return;
    }

    setAccessToken(result?.access_token);

    setTokens(result);

    setDisplaySignin(false);

    if (isSigning) {
      navigate("/");
    }
  };

  if (!displaySignIn && accessToken) {
    const data = parseJwt(accessToken);

    const auth = {
      accessToken,
      data,
      permissions: {
        write: WRITE_ROLES.includes(data?.user_claims?.role),
        isAdmin: ADMIN_ROLES.includes(data?.user_claims?.role),
      },
      signOut,
    } as tAuthContext;

    return (
      <AuthContext.Provider value={auth}>
        <AppComponent {...props} />
      </AuthContext.Provider>
    );
  }

  if (!displaySignIn && config?.main?.allow_anonymous_access) {
    const auth = {
      displaySignIn: () => setDisplaySignin(true),
    } as tAuthContext;

    return (
      <AuthContext.Provider value={auth}>
        <AppComponent {...props} />
      </AuthContext.Provider>
    );
  }

  return <SignIn isLoading={isLoading} onSubmit={signIn} />;
};
