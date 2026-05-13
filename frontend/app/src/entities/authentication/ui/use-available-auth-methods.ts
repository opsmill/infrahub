import type { AuthMethod } from "@/entities/authentication/types";
import { useConfig } from "@/entities/config/ui/config-provider";

export function useAvailableAuthMethods(): Array<AuthMethod> {
  const { sso } = useConfig();
  const methods: Array<AuthMethod> = [{ kind: "local", label: "Username & password" }];

  if (sso?.enabled && sso.providers && sso.providers.length > 0) {
    methods.push({ kind: "sso", providers: sso.providers });
  }

  return methods;
}
