import { mutationOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { loginWithLdap } from "@/entities/authentication/domain/login-with-ldap";

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
      // Logging in may be a different user than whatever cached data we hold
      // (re-auth after token expiry, switching accounts, etc.). Wipe the
      // entire cache so no prior user's data leaks into the new session —
      // mirrors the `queryClient.clear()` in logout.
      queryClient.clear();
    },
  });
}
