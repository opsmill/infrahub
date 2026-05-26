import { useMutation } from "@tanstack/react-query";

import { updateAccountPassword } from "@/entities/user-profile/domain/update-account-password";

export function useUpdateAccountPasswordMutation() {
  return useMutation({
    mutationFn: updateAccountPassword,
  });
}
