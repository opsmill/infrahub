import { useMutation } from "@tanstack/react-query";

import { removeDropdown } from "@/entities/schema/domain/remove-dropdown";

export function useRemoveDropdownMutation() {
  return useMutation({
    mutationFn: removeDropdown,
  });
}
