import type { AuthMethod } from "@/entities/authentication/types";
import type { ConfigAPI } from "@/entities/config/types";
import { useConfig } from "@/entities/config/ui/config-provider";

type MethodResolver = (config: ConfigAPI) => Array<AuthMethod>;

const METHOD_RESOLVERS: Array<MethodResolver> = [
  () => [{ kind: "local", label: "Username & password" }],
  ({ sso }) =>
    sso?.enabled && sso.providers?.length ? [{ kind: "sso", providers: sso.providers }] : [],
];

export function useAvailableAuthMethods(): Array<AuthMethod> {
  const config = useConfig();
  return METHOD_RESOLVERS.flatMap((resolve) => resolve(config));
}
