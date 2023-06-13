import { useAtom } from "jotai";
import { createContext, useEffect, useState } from "react";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../components/alert";
import { CONFIG } from "../config/config";
import { ACCESS_TOKEN_KEY } from "../config/constants";
import LoadingScreen from "../screens/loading-screen/loading-screen";
import SignIn from "../screens/sign-in/sign-in";
import { configState } from "../state/atoms/config.atom";
import { parseJwt } from "../utils/common";
import { fetchUrl } from "../utils/fetch";

// Export auth context
export const AuthContext = createContext(null);

// Add auth data in compo
export const withAuth = (AppComponent: any) => (props: any) => {
  const [config] = useAtom(configState);

  const [isLoadingToken, setIsLoadingToken] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [accessToken, setAccessToken] = useState("");

  useEffect(() => {
    const localToken = sessionStorage.getItem(ACCESS_TOKEN_KEY);

    if (localToken) {
      const data = parseJwt(localToken);
      console.log("data: ", data);

      setAccessToken(localToken);
    }

    setIsLoadingToken(false);
  }, []);

  const signOut = () => {
    sessionStorage.removeItem(ACCESS_TOKEN_KEY);
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
    sessionStorage.setItem(ACCESS_TOKEN_KEY, result?.access_token);
  };

  if (isLoadingToken) {
    // Loading screen while loadign the token from the lcoal storage
    return (
      <div className="w-screen h-screen flex ">
        <LoadingScreen />;
      </div>
    );
  }

  if (accessToken) {
    const auth = {
      accessToken,
      signOut,
    };

    console.log("auth: ", auth);
    return (
      <AuthContext.Provider value={auth}>
        <AppComponent {...props} />
      </AuthContext.Provider>
    );
  }

  if (config?.experimental_features?.ignore_authentication_requirements) {
    return (
      <AuthContext.Provider value={null}>
        <AppComponent {...props} />
      </AuthContext.Provider>
    );
  }

  // if (config?.main?.allow_anonymous_access) {
  //   return (
  //     <AuthContext.Provider value={null}>
  //       <AppComponent {...props} />
  //     </AuthContext.Provider>
  //   );
  // }

  return <SignIn isLoading={isLoading} onSubmit={signIn} />;
};

// Get access for pages from rights
export const getAccess = (page: any, rights: any = {}) => {
  if (page.agent) {
    return rights.isAdmin || rights.isAgent;
  }

  if (page.provider) {
    return rights.isAdmin || rights.isProvider;
  }

  if (page.admin) {
    return rights.isAdmin;
  }

  return !page.provider;
};
