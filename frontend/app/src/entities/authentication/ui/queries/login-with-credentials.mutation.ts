import { mutationOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { loginWithCredentials } from "@/entities/authentication/domain/login-with-credentials";

export function loginWithCredentialsMutationOptions() {
  return mutationOptions({
    mutationKey: ["login-with-credentials"],
    mutationFn: loginWithCredentials,
  });
}

export function useLoginWithCredentials() {
  const queryClient = useQueryClient();

  return useMutation({
    ...loginWithCredentialsMutationOptions(),
    onSuccess: () => {
      // Logging in may be a different user than whatever cached data we hold
      // (re-auth after token expiry, switching accounts, etc.). Wipe the
      // entire cache so no prior user's data leaks into the new session —
      // mirrors the `queryClient.clear()` in logout.
      queryClient.clear();
    },
  });
}
