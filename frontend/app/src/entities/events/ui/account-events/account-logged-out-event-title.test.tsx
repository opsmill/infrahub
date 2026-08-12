import { describe, expect, test } from "vitest";

import type { AccountLoggedOutEventType } from "@/shared/api/graphql/generated/types";

import { render } from "../../../../../tests/components/render";
import { AccountLoggedOutEventTitle } from "./account-logged-out-event-title";

const logoutEvent: AccountLoggedOutEventType = {
  id: "42156a81-9cbe-40e4-b306-3e5e74f643a0",
  event: "infrahub.account.logged_out",
  branch: "main",
  occurred_at: "2026-04-06T11:19:42.703363+00:00",
  level: 0,
  account_id: "18a2e82f-a691-da86-3398-c510d9def364",
  primary_node: {
    id: "18a2e82f-a691-da86-3398-c510d9def364",
    kind: "CoreAccount",
    __typename: "RelatedNode",
  },
  related_nodes: [],
  has_children: false,
  __typename: "AccountLoggedOutEventType",
  account_name: "admin",
  client_ip: null,
  kind: "CoreAccount",
  logout_type: "user_initiated",
  parent_id: null,
  payload: {},
  session_id: "18a3c089-085a-ac67-38d1-c5139dd74202",
  timestamp: "2026-04-06T11:19:42.702056+00:00",
  user_agent: null,
};

describe("AccountLoggedOutEventTitle", () => {
  test("renders logout event", async () => {
    // GIVEN
    const component = await render(<AccountLoggedOutEventTitle {...logoutEvent} />);

    // THEN
    await expect.element(component.getByText("logged out")).toBeVisible();
  });
});
