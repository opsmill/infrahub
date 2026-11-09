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
