import { useEffect, useState } from "react";
import { Navigate, useParams, useSearchParams } from "react-router";

import { FetchError, fetchUrl, type RestErrorItem } from "@/shared/api/rest/fetch";
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
  const [errors, setErrors] = useState<RestErrorItem[] | null>(null);

  const code = searchParams.get("code");
  const state = searchParams.get("state");

  // Reduce the effect's deps to stable scalars. `config` is an object
  // whose reference may change every time `useGetConfig` refetches —
  // depending on it directly would re-fire the SSO token exchange on
  // each refetch tick. The token exchange is one-shot, so re-running it
  // would either succeed-then-error (code already consumed) or
  // accidentally double-set tokens. The fields below are the only ones
  // the effect actually reads.
  const ssoEnabled = config?.sso?.enabled ?? false;
  const tokenPath = config?.sso?.providers?.find(
    (p) => p.protocol === protocol && p.name === provider
  )?.token_path;

  useEffect(() => {
    if (!ssoEnabled || !tokenPath) return;

    const callbackUrl = new URL(`${INFRAHUB_API_SERVER_URL}${tokenPath}`);
    if (code) callbackUrl.searchParams.set("code", code);
    if (state) callbackUrl.searchParams.set("state", state);

    fetchUrl(callbackUrl.toString())
      .then((result) => {
        // 2xx response that still carries `errors` — normalise to a
        // FetchError so the catch sees the same shape as a non-2xx
        // failure (single typed envelope, no `any` cast needed).
        if (result.errors) {
          throw new FetchError(200, result.errors);
        }

        setRedirectTo(result.final_url);
        setToken(result);
      })
      .catch((error: unknown) => {
        if (error instanceof FetchError && error.errors) {
          setErrors(error.errors);
          return;
        }
        // Non-envelope failure (network error, unexpected throw, or a
        // FetchError without an `errors` array). Surface a generic envelope
        // so the user is bounced to /login with a visible message instead
        // of being stuck on the loading screen.
        //
        // `code: 0` is the local sentinel for "frontend-synthesised error,
        // no backend code" — LoginPage renders the number verbatim, so 0
        // signals to readers (not to users) that this entry was forged here.
        console.error("[auth-callback] unexpected failure", error);
        setErrors([
          {
            message: "Failed to complete sign-in. Please try again.",
            extensions: { code: 0 },
          },
        ]);
      });
  }, [ssoEnabled, tokenPath, code, state, setToken]);

  if (!ssoEnabled) {
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
