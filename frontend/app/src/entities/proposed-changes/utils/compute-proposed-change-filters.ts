import { Filter } from "@/shared/hooks/useFilters";
import { PROPOSED_CHANGE_STATES } from "../constants";

export const computeProposedChangeFilters = ({
  filters,
  state,
}: { filters: Array<Filter>; state: keyof typeof PROPOSED_CHANGE_STATES | string }) => {
  return [
    ...filters,
    {
      name: "state__values",
      value:
        state && state in PROPOSED_CHANGE_STATES
          ? PROPOSED_CHANGE_STATES[state as keyof typeof PROPOSED_CHANGE_STATES]
          : PROPOSED_CHANGE_STATES.opened,
    } as Filter,
  ];
};
