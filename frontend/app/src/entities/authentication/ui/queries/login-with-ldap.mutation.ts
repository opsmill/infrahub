import { mutationOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { loginWithLdap } from "@/entities/authentication/domain/login-with-ldap";
import { accountQueryKeys } from "@/entities/user-profile/ui/queries/account-query.keys";

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
      queryClient.invalidateQueries({ queryKey: accountQueryKeys.all });
    },
  });
}
