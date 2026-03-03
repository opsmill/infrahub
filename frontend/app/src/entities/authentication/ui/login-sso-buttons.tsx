import { Icon } from "@iconify-icon/react";
import { useLocation } from "react-router";

import { INFRAHUB_API_SERVER_URL } from "@/shared/config/config";
import { classNames } from "@/shared/utils/common";

import type { SSOProvider } from "@/entities/config/types";

export interface LoginWithSSOButtonsProps {
  className?: string;
  providers: Array<SSOProvider>;
}

export const LoginWithSSOButtons = ({ className, providers }: LoginWithSSOButtonsProps) => {
  const location = useLocation();
  const redirectTo: string =
    (location.state?.from?.pathname || "/") + (location.state?.from?.search ?? "");

  return (
    <div className={classNames("flex w-full flex-col gap-2", className)}>
      {providers.map((provider) => (
        <ProviderButton
          key={`${provider.name}-${provider.protocol}`}
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
  return (
    <a
      className="inline-flex h-9 items-center justify-center whitespace-nowrap rounded-md border border-gray-200 bg-white px-4 py-2 font-medium text-sm shadow-xs hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60"
      href={`${INFRAHUB_API_SERVER_URL + provider.authorizePath}?final_url=${redirectTo}`}
    >
      <Icon icon={provider.icon} />
      <span className="ml-2">Continue with {provider.displayLabel}</span>
    </a>
  );
};
