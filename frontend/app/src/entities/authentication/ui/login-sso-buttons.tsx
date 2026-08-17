import { LinkButton } from "@infrahub/ui";
import { useLocation, useSearchParams } from "react-router";

import { Icon } from "@/shared/components/display/icon";
import { INFRAHUB_API_SERVER_URL } from "@/shared/config/config";
import { classNames } from "@/shared/utils/common";

import {
  pathToString,
  resolveLoginRedirect,
} from "@/entities/authentication/ui/routing/login-redirect";
import type { SSOProvider } from "@/entities/config/domain/model/config";

export interface LoginWithSSOButtonsProps {
  className?: string;
  providers: Array<SSOProvider>;
}

export const LoginWithSSOButtons = ({ className, providers }: LoginWithSSOButtonsProps) => {
  const location = useLocation();
  const [searchParams] = useSearchParams();

  // Backend echoes back `final_url` as-is, so SSO sign-in must use the
  // same redirect target as in-app sign-in or hard-navigated users land
  // at "/" instead of where they came from.
  const redirectTo = pathToString(resolveLoginRedirect(location, searchParams));

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
    <LinkButton variant="outline" href={authorizeUrl} className="font-medium">
      <Icon icon={provider.icon} />
      Continue with {provider.display_label}
    </LinkButton>
  );
};
