import type { ReactNode } from "react";

import type { AuthMethod, AuthMethodKind } from "@/entities/authentication/types";
import { LocalCredentialsForm } from "@/entities/authentication/ui/local-credentials-form";
import { LoginWithSSOButtons } from "@/entities/authentication/ui/login-sso-buttons";
import type { ConfigAPI } from "@/entities/config/types";

type AuthMethodDefinition<K extends AuthMethodKind> = {
  kind: K;
  toggleLabel: string;
  preferDefault: boolean;
  resolve: (config: ConfigAPI) => Extract<AuthMethod, { kind: K }> | null;
  render: (method: Extract<AuthMethod, { kind: K }>) => ReactNode;
};

type AuthMethodRegistry = {
  [K in AuthMethodKind]: AuthMethodDefinition<K>;
};

export const AUTH_METHODS: AuthMethodRegistry = {
  local: {
    kind: "local",
    toggleLabel: "Log in with your credentials",
    preferDefault: false,
    resolve: () => ({ kind: "local" }),
    render: () => <LocalCredentialsForm className="fade-in animate-in" />,
  },
  sso: {
    kind: "sso",
    toggleLabel: "Log in with SSO",
    preferDefault: true,
    resolve: (config) => {
      const sso = config.sso;
      if (!sso?.enabled || !sso.providers || sso.providers.length === 0) return null;
      return { kind: "sso", providers: sso.providers };
    },
    render: (method) => (
      <LoginWithSSOButtons providers={method.providers} className="fade-in animate-in" />
    ),
  },
};

export function getAuthMethodDefinition<K extends AuthMethodKind>(
  kind: K
): AuthMethodDefinition<K> {
  return AUTH_METHODS[kind];
}

export function resolveAvailableAuthMethods(config: ConfigAPI): Array<AuthMethod> {
  return Object.values(AUTH_METHODS)
    .map((def) => (def.resolve as (c: ConfigAPI) => AuthMethod | null)(config))
    .filter((m): m is AuthMethod => m !== null);
}
