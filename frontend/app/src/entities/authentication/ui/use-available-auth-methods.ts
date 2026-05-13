import { resolveAvailableAuthMethods } from "@/entities/authentication/auth-methods";
import type { AuthMethod } from "@/entities/authentication/types";
import { useConfig } from "@/entities/config/ui/config-provider";

export function useAvailableAuthMethods(): Array<AuthMethod> {
  return resolveAvailableAuthMethods(useConfig());
}
