import type { LoginError, LoginErrorCode } from "@/entities/authentication/types";

export const ACCESS_TOKEN_KEY = "access_token";
export const REFRESH_TOKEN_KEY = "refresh_token";
export const LAST_USED_METHOD_KEY = "auth_last_used_method";

export const LOGIN_ERRORS: Record<LoginErrorCode, LoginError> = {
  invalid_credentials: {
    code: "invalid_credentials",
    message: "Invalid username or password",
  },
  account_collision: {
    code: "account_collision",
    message: "An account with this username already exists",
  },
  enterprise_required: {
    code: "enterprise_required",
    message: "This authentication method requires the enterprise edition",
  },
  server: {
    code: "server",
    message: "Authentication service unavailable",
  },
  network: {
    code: "network",
    message: "Network error — check your connection",
  },
  unknown: {
    code: "unknown",
    message: "Could not log in",
  },
};
