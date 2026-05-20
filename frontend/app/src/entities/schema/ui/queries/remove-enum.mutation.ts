import { useMutation } from "@tanstack/react-query";

import { removeEnum } from "@/entities/schema/domain/remove-enum";

export function useRemoveEnumMutation() {
  return useMutation({
    mutationFn: removeEnum,
  });
}
