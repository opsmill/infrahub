import { mutationOptions, useMutation } from "@tanstack/react-query";

import { logout } from "@/entities/authentication/domain/logout";

export function logoutMutationOptions() {
  return mutationOptions({
    mutationKey: ["logout"],
    mutationFn: logout,
  });
}

export function useLogoutMutation() {
  return useMutation(logoutMutationOptions());
}
