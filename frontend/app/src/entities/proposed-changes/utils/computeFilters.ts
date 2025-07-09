import { PROPOSED_CHANGE_STATES } from "./constant";

export const computeFilters = ({ filters, state }) => {
  return [
    ...filters,
    {
      name: "state__values",
      value: state
        ? (PROPOSED_CHANGE_STATES[state] ?? PROPOSED_CHANGE_STATES.opened)
        : PROPOSED_CHANGE_STATES.opened,
    },
  ];
};
