import { INFRAHUB_API_SERVER_URL } from "@/config/config";
import { useAuth } from "@/hooks/useAuth";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { configState } from "@/state/atoms/config.atom";
import { fetchUrl } from "@/utils/fetch";
import { useAtomValue } from "jotai";
import { useEffect, useState } from "react";
import { Navigate, useParams, useSearchParams } from "react-router-dom";

function AuthCallback() {
  const { protocol, provider } = useParams();
  const config = useAtomValue(configState);
  const [searchParams] = useSearchParams();
  const { isAuthenticated, setToken } = useAuth();
  const [redirectTo, setRedirectTo] = useState("/");
  const [errors, setErrors] = useState(null);

  const code = searchParams.get("code");
  const state = searchParams.get("state");

  useEffect(() => {
    if (!config || !config.sso.enabled) return;

    const currentAuthProvider = config.sso.providers.find(
      (p) => p.protocol === protocol && p.name === provider
    );
    if (!currentAuthProvider) return;

    const { token_path } = currentAuthProvider;
    fetchUrl(`${INFRAHUB_API_SERVER_URL}${token_path}?code=${code}&state=${state}`)
      .then((result) => {
        if (result.errors) {
          throw result;
        }

        setRedirectTo(result.final_url);
        setToken(result);
      })
      .catch((error) => {
        setErrors(error.errors);
      });
  }, [config, protocol, provider]);

  if (!config || !config.sso.enabled) {
    return <Navigate to="/login" replace />;
  }

  if (errors) {
    return <Navigate to="/login" state={{ errors }} replace />;
  }

  if (isAuthenticated) {
    return <Navigate to={redirectTo} replace />;
  }

  return (
    <div className="w-screen h-screen flex items-center justify-center">
      <LoadingScreen />
    </div>
  );
}

export const Component = AuthCallback;
