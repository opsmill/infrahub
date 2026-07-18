import type { components } from "@/shared/api/rest/types.generated";

export type User = {
  id: string;
};

export type UserToken = components["schemas"]["UserToken"];

export type LoginErrorCode =
  | "invalid_credentials"
  | "account_collision"
  | "enterprise_required"
  | "network"
  | "server"
  | "unknown";

export type LoginError = {
  code: LoginErrorCode;
  message: string;
};
