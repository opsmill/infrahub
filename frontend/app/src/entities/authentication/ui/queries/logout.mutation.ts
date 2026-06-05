import { mutationOptions, useMutation } from "@tanstack/react-query";

import { logout } from "@/entities/authentication/domain/logout";

// invalidation-at-callsite: logout flushes the entire client cache via
// `queryClient.clear()` in account-menu.tsx — that wipes more than any single
// queryKey we could invalidate here.
export function logoutMutationOptions() {
  return mutationOptions({
    mutationKey: ["logout"],
    mutationFn: logout,
  });
}

export function useLogoutMutation() {
  return useMutation(logoutMutationOptions());
}
