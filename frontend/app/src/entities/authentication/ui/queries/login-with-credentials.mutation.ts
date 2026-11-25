import { mutationOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { loginWithCredentials } from "@/entities/authentication/domain/use-cases/login-with-credentials";
import { clearSessionCache } from "@/entities/authentication/ui/queries/clear-session-cache";

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
      clearSessionCache(queryClient);
    },
  });
}
