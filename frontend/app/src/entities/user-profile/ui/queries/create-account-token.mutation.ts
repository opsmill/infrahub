import { useMutation } from "@tanstack/react-query";

import { createAccountToken } from "@/entities/user-profile/domain/create-account-token";

export function useCreateAccountTokenMutation() {
  return useMutation({
    mutationFn: createAccountToken,
  });
}
