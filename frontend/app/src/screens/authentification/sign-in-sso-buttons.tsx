import { Provider } from "@/state/atoms/config.atom";
import { LinkButton } from "@/components/buttons/button-primitive";
import { Icon } from "@iconify-icon/react";
import { INFRAHUB_API_SERVER_URL } from "@/config/config";

export const SignInWithSSOButtons = ({ providers }: { providers: Array<Provider> }) => {
  return providers.map((provider) => (
    <ProviderButton key={provider.name + provider.protocol} provider={provider} />
  ));
};

export const ProviderButton = ({ provider }: { provider: Provider }) => {
  return (
    <LinkButton
      variant="outline"
      className="w-full"
      to={INFRAHUB_API_SERVER_URL + provider.authorize_path}>
      <Icon icon={provider.icon} />
      <span className="ml-2">Sign in with {provider.display_label}</span>
    </LinkButton>
  );
};
