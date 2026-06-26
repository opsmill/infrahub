import { useMutation, useQueryClient } from "@tanstack/react-query";

import { createAccountToken } from "@/entities/user-profile/domain/create-account-token";
import { accountQueryKeys } from "@/entities/user-profile/ui/queries/account-query.keys";

export function useCreateAccountTokenMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createAccountToken,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: accountQueryKeys.tokens() });
    },
  });
}
