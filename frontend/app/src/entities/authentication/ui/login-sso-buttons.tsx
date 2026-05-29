import { Icon } from "@iconify-icon/react";
import { type Path, useLocation, useSearchParams } from "react-router";

import { INFRAHUB_API_SERVER_URL } from "@/shared/config/config";
import { classNames } from "@/shared/utils/common";

import { pathToString, safeInternalPath } from "@/entities/authentication/utils";
import type { SSOProvider } from "@/entities/config/types";

export interface LoginWithSSOButtonsProps {
  className?: string;
  providers: Array<SSOProvider>;
}

export const LoginWithSSOButtons = ({ className, providers }: LoginWithSSOButtonsProps) => {
  const location = useLocation();
  const [searchParams] = useSearchParams();

  // Mirror the resolution order used by LoginPage so SSO sign-in returns
  // the user to the same destination as in-app sign-in: prefer router
  // state (set by ProtectedRoute), fall back to the `?from=` query param
  // set by `redirectToLogin()` on hard nav. Without this fallback, users
  // hard-navigated to `/login?from=/x` and then clicking an SSO button
  // would land at `/` after auth-callback because the backend only knows
  // what we put in `final_url`.
  const stateFrom = location.state?.from as Partial<Path> | undefined;
  const queryFrom = safeInternalPath(searchParams.get("from"));
  const redirectTo = pathToString(stateFrom ?? queryFrom ?? { pathname: "/" });

  return (
    <div className={classNames("flex w-full flex-col gap-2", className)}>
      {providers.map((provider) => (
        <ProviderButton
          key={provider.name + provider.protocol}
          provider={provider}
          redirectTo={redirectTo}
        />
      ))}
    </div>
  );
};

export const ProviderButton = ({
  provider,
  redirectTo = "/",
}: {
  provider: SSOProvider;
  redirectTo?: string;
}) => {
  // Encode `final_url` so a redirect target that contains `&` or `?` does
  // not corrupt the authorize URL's own query string.
  const authorizeUrl = `${INFRAHUB_API_SERVER_URL + provider.authorize_path}?final_url=${encodeURIComponent(redirectTo)}`;

  return (
    <a
      className="inline-flex h-9 items-center justify-center whitespace-nowrap rounded-md border border-gray-200 bg-white px-4 py-2 font-medium text-sm shadow-xs hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60"
      href={authorizeUrl}
    >
      <Icon icon={provider.icon} />
      <span className="ml-2">Continue with {provider.display_label}</span>
    </a>
  );
};
