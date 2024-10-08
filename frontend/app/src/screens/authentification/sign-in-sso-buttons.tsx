import { INFRAHUB_API_SERVER_URL } from "@/config/config";
import { Provider } from "@/state/atoms/config.atom";
import { Icon } from "@iconify-icon/react";
import { useLocation } from "react-router-dom";

export const SignInWithSSOButtons = ({ providers }: { providers: Array<Provider> }) => {
  let location = useLocation();
  const redirectTo: string =
    (location.state?.from?.pathname || "/") + (location.state?.from?.search ?? "");

  return (
    <div className="flex flex-col space-y-1 w-full">
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
}: { provider: Provider; redirectTo?: string }) => {
  return (
    <a
      className="h-9 px-4 py-2 inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium disabled:opacity-60 disabled:cursor-not-allowed border bg-custom-white shadow-sm hover:bg-gray-100"
      href={`${INFRAHUB_API_SERVER_URL + provider.authorize_path}?final_url=${redirectTo}`}
    >
      <Icon icon={provider.icon} />
      <span className="ml-2">Sign in with {provider.display_label}</span>
    </a>
  );
};
