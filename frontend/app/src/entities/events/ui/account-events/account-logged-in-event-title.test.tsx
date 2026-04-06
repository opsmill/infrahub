import { describe, expect, test } from "vitest";

import type { AccountLoggedInEventType } from "@/shared/api/graphql/generated/types";

import { render } from "../../../../../tests/components/render";
import { AccountLoggedInEventTitle } from "./account-logged-in-event-title";

const loginEvent: AccountLoggedInEventType = {
  id: "7dfb5bf2-d0ad-4a06-bfd3-d0916b5b904e",
  event: "infrahub.account.logged_in",
  branch: "main",
  occurred_at: "2026-04-06T21:29:30.290070+00:00",
  level: 0,
  account_id: "18a2e83c-0e80-fa90-3392-c51809fb54cf",
  primary_node: {
    id: "18a2e83c-0e80-fa90-3392-c51809fb54cf",
    kind: "CoreAccount",
    __typename: "RelatedNode",
  },
  related_nodes: [
    {
      id: "18a2e83c-5415-e0f3-3399-c51c3c6f3398",
      kind: "CoreAccountGroup",
      __typename: "RelatedNode",
    },
    {
      id: "18a2e83b-ede8-1469-339b-c511801ec083",
      kind: "CoreAccountRole",
      __typename: "RelatedNode",
    },
  ],
  has_children: false,
  __typename: "AccountLoggedInEventType",
  account_name: "jbauer",
  account_type: "User",
  auth_method: "password",
  client_ip: null,
  groups: [],
  identity_source: null,
  kind: "CoreAccount",
  parent_id: null,
  payload: {},
  roles: [],
  session_id: "18a3e1d1-efbe-bd53-38db-c51848891c21",
  timestamp: "2026-04-06T21:29:30.290003+00:00",
  user_agent: null,
};

describe("AccountLoggedInEventTitle", () => {
  test("renders login with password auth method", async () => {
    // GIVEN
    const component = await render(<AccountLoggedInEventTitle {...loginEvent} />);

    // THEN
    await expect.element(component.getByText("logged in via password")).toBeVisible();
  });

  test("renders login with OAuth2 auth method", async () => {
    // GIVEN
    const component = await render(
      <AccountLoggedInEventTitle {...loginEvent} auth_method="OAUTH2" />
    );

    // THEN
    await expect.element(component.getByText("logged in via OAuth2")).toBeVisible();
  });
});
