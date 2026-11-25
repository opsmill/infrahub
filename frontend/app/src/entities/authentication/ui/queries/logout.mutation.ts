import { mutationOptions, useMutation } from "@tanstack/react-query";

import { logout } from "@/entities/authentication/domain/use-cases/logout";

// invalidation-at-callsite: signing out clears the session cache, which
// covers more than any single queryKey we could invalidate here.
export function logoutMutationOptions() {
  return mutationOptions({
    mutationKey: ["logout"],
    mutationFn: logout,
  });
}

export function useLogoutMutation() {
  return useMutation(logoutMutationOptions());
}
