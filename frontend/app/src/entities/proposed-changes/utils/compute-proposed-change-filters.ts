import type { Filter } from "@/shared/hooks/useFilters";

import { PROPOSED_CHANGE_STATES, STATE_VALUES_FILTER } from "@/entities/proposed-changes/constants";

export const computeProposedChangeFilters = ({
  filters,
  qsp,
}: {
  filters: Array<Filter>;
  qsp: keyof typeof PROPOSED_CHANGE_STATES | string;
}) => {
  const stateFilter: Filter = {
    name: STATE_VALUES_FILTER,
    value:
      qsp && qsp in PROPOSED_CHANGE_STATES
        ? PROPOSED_CHANGE_STATES[qsp as keyof typeof PROPOSED_CHANGE_STATES]
        : PROPOSED_CHANGE_STATES.opened,
  };

  return [...filters, stateFilter];
};
