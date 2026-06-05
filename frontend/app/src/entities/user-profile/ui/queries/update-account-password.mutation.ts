import { useMutation } from "@tanstack/react-query";

import { updateAccountPassword } from "@/entities/user-profile/domain/update-account-password";

// invalidation-at-callsite: password updates do not change any data we cache —
// the credential lives in the auth backend and the access token is rotated
// independently. No query key needs refreshing.
export function useUpdateAccountPasswordMutation() {
  return useMutation({
    mutationFn: updateAccountPassword,
  });
}
