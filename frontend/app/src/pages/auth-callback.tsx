import { useEffect, useState } from "react";
import { Navigate, useParams, useSearchParams } from "react-router";

import { fetchUrl } from "@/shared/api/rest/fetch";
import { InfrahubLoading } from "@/shared/components/loading/infrahub-loading";
import { INFRAHUB_API_SERVER_URL } from "@/shared/config/config";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { useConfig } from "@/entities/config/ui/config-provider";

function AuthCallback() {
  const { protocol, provider } = useParams();
  const config = useConfig();
  const [searchParams] = useSearchParams();
  const { isAuthenticated, setToken } = useAuth();
  const [redirectTo, setRedirectTo] = useState("/");
  const [errors, setErrors] = useState(null);

  const code = searchParams.get("code");
  const state = searchParams.get("state");

  useEffect(() => {
    if (!config || !config.sso.enabled) return;

    const currentAuthProvider = config.sso.providers?.find(
      (p) => p.protocol === protocol && p.name === provider
    );
    if (!currentAuthProvider) return;

    const { tokenPath } = currentAuthProvider;
    fetchUrl(`${INFRAHUB_API_SERVER_URL}${tokenPath}?code=${code}&state=${state}`)
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

  return <InfrahubLoading>Authenticating...</InfrahubLoading>;
}

export const Component = AuthCallback;
