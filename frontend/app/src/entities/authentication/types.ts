import type { components } from "@/shared/api/rest/types.generated";

import type { SSOProvider } from "@/entities/config/types";

export type User = {
  id: string;
};

export type UserToken = components["schemas"]["UserToken"];

export type LoginErrorCode = "invalid_credentials" | "network" | "server" | "unknown";

export type LoginError = {
  code: LoginErrorCode;
  message: string;
};

export type AuthMethod = { kind: "local" } | { kind: "sso"; providers: Array<SSOProvider> };
// Future: | { kind: "ldap" };

export type AuthMethodKind = AuthMethod["kind"];
