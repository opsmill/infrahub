import { useMutation } from "@tanstack/react-query";

import { addDropdown } from "@/entities/schema/domain/add-dropdown";

export function useAddDropdownMutation() {
  return useMutation({
    mutationFn: addDropdown,
  });
}
