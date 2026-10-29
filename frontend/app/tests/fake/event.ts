import type { StandardEvent } from "@/shared/api/graphql/generated/types";

export const generateEvent = (overrides?: Partial<StandardEvent>): StandardEvent => {
  return {
    __typename: "StandardEvent",
    id: "0f8a4c6e-2d1b-4e7a-9c3f-5b6d7e8f9a0b",
    event: "infrahub.node.created",
    account_id: null,
    branch: "main",
    has_children: false,
    level: 0,
    occurred_at: "2026-10-04T12:00:00.000100+00:00",
    parent_id: null,
    payload: {},
    primary_node: null,
    related_nodes: [],
    ...overrides,
  };
};
