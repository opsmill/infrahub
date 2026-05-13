import type { AuthMethod } from "@/entities/authentication/types";
import { useConfig } from "@/entities/config/ui/config-provider";

export function useAvailableAuthMethods(): Array<AuthMethod> {
  const config = useConfig();

  const methods: Array<AuthMethod> = [{ kind: "local", label: "Username & password" }];

  if (config?.sso?.enabled && config.sso.providers && config.sso.providers.length > 0) {
    methods.push({ kind: "sso", providers: config.sso.providers });
  }

  return methods;
}
