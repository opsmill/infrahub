import { useMutation } from "@tanstack/react-query";

import { addEnum } from "@/entities/schema/domain/add-enum";

export function useAddEnumMutation() {
  return useMutation({
    mutationFn: addEnum,
  });
}
