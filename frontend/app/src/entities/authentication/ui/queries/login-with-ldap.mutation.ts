import { mutationOptions, useMutation } from "@tanstack/react-query";

import { loginWithLdap } from "@/entities/authentication/domain/login-with-ldap";

export function loginWithLdapMutationOptions() {
  return mutationOptions({
    mutationKey: ["login-with-ldap"],
    mutationFn: loginWithLdap,
  });
}

export function useLoginWithLdap() {
  return useMutation(loginWithLdapMutationOptions());
}
