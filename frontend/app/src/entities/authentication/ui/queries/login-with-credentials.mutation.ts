import { mutationOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { loginWithCredentials } from "@/entities/authentication/domain/login-with-credentials";
import { accountQueryKeys } from "@/entities/user-profile/ui/queries/account-query.keys";

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
      queryClient.invalidateQueries({ queryKey: accountQueryKeys.all });
    },
  });
}
