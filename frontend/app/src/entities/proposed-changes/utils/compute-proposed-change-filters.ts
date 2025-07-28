import { Filter } from "@/shared/hooks/useFilters";
import { DRAFT_STATE, PROPOSED_CHANGE_STATES } from "../constants";

export const computeProposedChangeFilters = ({
  filters,
  qsp,
}: { filters: Array<Filter>; qsp: keyof typeof PROPOSED_CHANGE_STATES | string }) => {
  return [
    ...filters,
    {
      name: "state__values",
      value:
        qsp && qsp in PROPOSED_CHANGE_STATES
          ? PROPOSED_CHANGE_STATES[qsp as keyof typeof PROPOSED_CHANGE_STATES]
          : PROPOSED_CHANGE_STATES.opened,
    } as Filter,
    qsp === DRAFT_STATE &&
      ({
        name: "is_draft__value",
        value: true,
      } as Filter),
  ];
};
