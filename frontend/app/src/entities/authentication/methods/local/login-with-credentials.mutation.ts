import { mutationOptions, useMutation } from "@tanstack/react-query";

import { loginWithCredentials } from "@/entities/authentication/methods/local/login-with-credentials";

export function loginWithCredentialsMutationOptions() {
  return mutationOptions({
    mutationKey: ["login-with-credentials"],
    mutationFn: loginWithCredentials,
  });
}

export function useLoginWithCredentials() {
  return useMutation(loginWithCredentialsMutationOptions());
}
