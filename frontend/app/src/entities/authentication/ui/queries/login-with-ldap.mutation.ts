import { mutationOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { loginWithLdap } from "@/entities/authentication/domain/use-cases/login-with-ldap";
import { clearSessionCache } from "@/entities/authentication/ui/queries/clear-session-cache";

export function loginWithLdapMutationOptions() {
  return mutationOptions({
    mutationKey: ["login-with-ldap"],
    mutationFn: loginWithLdap,
  });
}

export function useLoginWithLdap() {
  const queryClient = useQueryClient();

  return useMutation({
    ...loginWithLdapMutationOptions(),
    onSuccess: () => {
      clearSessionCache(queryClient);
    },
  });
}
