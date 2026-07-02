import {
  type AuthMethod,
  resolveAvailableAuthMethods,
} from "@/entities/authentication/ui/auth-methods";
import { useConfig } from "@/entities/config/ui/config-provider";

export function useAvailableAuthMethods(): Array<AuthMethod> {
  return resolveAvailableAuthMethods(useConfig());
}
