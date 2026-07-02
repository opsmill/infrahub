import type { ReactNode } from "react";

import { LdapCredentialsForm } from "@/entities/authentication/ui/ldap-credentials-form";
import { LocalCredentialsForm } from "@/entities/authentication/ui/local-credentials-form";
import { LoginWithSSOButtons } from "@/entities/authentication/ui/login-sso-buttons";
import type { ConfigAPI, SSOProvider } from "@/entities/config/types";

// Runtime data for each auth method.
// Adding a method = adding a variant here and an entry in AUTH_METHODS.
export type AuthMethod =
  | { kind: "local" }
  | { kind: "sso"; providers: Array<SSOProvider> }
  | { kind: "ldap"; displayLabel: string; icon: string };

export type AuthMethodKind = AuthMethod["kind"];

type AuthMethodDefinition<TMethod extends AuthMethod> = {
  toggleLabel: (method: TMethod) => ReactNode;
  preferDefault: boolean;
  resolve: (config: ConfigAPI) => TMethod | null;
  render: (method: TMethod) => ReactNode;
};

type AuthMethodRegistry = {
  [K in AuthMethodKind]: AuthMethodDefinition<Extract<AuthMethod, { kind: K }>>;
};

export const AUTH_METHODS: AuthMethodRegistry = {
  local: {
    toggleLabel: () => "Log in with your credentials",
    preferDefault: false,
    resolve: () => ({ kind: "local" }),
    render: () => <LocalCredentialsForm className="fade-in animate-in" />,
  },
  sso: {
    toggleLabel: () => "Log in with SSO",
    preferDefault: true,
    resolve: (config) => {
      const sso = config.sso;
      if (!sso?.enabled || !sso.providers?.length) return null;
      return { kind: "sso", providers: sso.providers };
    },
    render: ({ providers }) => (
      <LoginWithSSOButtons providers={providers} className="fade-in animate-in" />
    ),
  },
  ldap: {
    toggleLabel: ({ displayLabel }) => displayLabel,
    preferDefault: false,
    resolve: (config) => {
      const ldap = config.ldap;
      if (!ldap?.enabled) return null;
      return { kind: "ldap", displayLabel: ldap.display_label, icon: ldap.icon };
    },
    render: ({ displayLabel, icon }) => (
      <LdapCredentialsForm displayLabel={displayLabel} icon={icon} className="fade-in animate-in" />
    ),
  },
};

// Helpers below isolate the per-variant casts that TS can't infer through
// a dynamic registry lookup. The casts are sound because the registry is
// keyed by `kind`, so `AUTH_METHODS[method.kind]` always matches `method`.

export function renderAuthMethod(method: AuthMethod): ReactNode {
  const def = AUTH_METHODS[method.kind] as AuthMethodDefinition<AuthMethod>;
  return def.render(method);
}

export function getAuthMethodToggleLabel(method: AuthMethod): ReactNode {
  const def = AUTH_METHODS[method.kind] as AuthMethodDefinition<AuthMethod>;
  return def.toggleLabel(method);
}

export function resolveAvailableAuthMethods(config: ConfigAPI): Array<AuthMethod> {
  const definitions = Object.values(AUTH_METHODS) as Array<AuthMethodDefinition<AuthMethod>>;
  return definitions.map((def) => def.resolve(config)).filter((m): m is AuthMethod => m !== null);
}
