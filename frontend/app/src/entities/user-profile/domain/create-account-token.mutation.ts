import { createAccountToken } from "@/entities/user-profile/domain/create-account-token";
import { useMutation } from "@tanstack/react-query";

export function useCreateAccountTokenMutation() {
  return useMutation({
    mutationFn: createAccountToken,
  });
}
