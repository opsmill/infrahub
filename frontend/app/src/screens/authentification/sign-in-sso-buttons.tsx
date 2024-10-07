import { INFRAHUB_API_SERVER_URL } from "@/config/config";
import { Provider } from "@/state/atoms/config.atom";
import { Icon } from "@iconify-icon/react";

export const SignInWithSSOButtons = ({ providers }: { providers: Array<Provider> }) => {
  return (
    <div className="flex flex-col space-y-1 w-full">
      {providers.map((provider) => (
        <ProviderButton key={provider.name + provider.protocol} provider={provider} />
      ))}
    </div>
  );
};

export const ProviderButton = ({ provider }: { provider: Provider }) => {
  return (
    <a
      className="h-9 px-4 py-2 inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium disabled:opacity-60 disabled:cursor-not-allowed border bg-custom-white shadow-sm hover:bg-gray-100"
      href={INFRAHUB_API_SERVER_URL + provider.authorize_path}
    >
      <Icon icon={provider.icon} />
      <span className="ml-2">Sign in with {provider.display_label}</span>
    </a>
  );
};
