import { describe, expect, test } from "vitest";

import type {
  GroupAutoCreateCappedEventType,
  GroupAutoCreatedEventType,
  GroupAutoCreateRejectedEventType,
} from "@/shared/api/graphql/generated/types";

import { render } from "../../../../../tests/components/render";
import { GroupAutoCreateEventTitle } from "./group-auto-create-event-title";

const baseEvent = {
  id: "7dfb5bf2-d0ad-4a06-bfd3-d0916b5b904e",
  branch: "main",
  occurred_at: "2026-04-06T21:29:30.290070+00:00",
  level: 0,
  account_id: null,
  primary_node: null,
  related_nodes: [],
  has_children: false,
  parent_id: null,
  payload: {},
  idp: "provider1",
  protocol: "oidc",
  triggering_user_id: "18a2e83c-0e80-fa90-3392-c51809fb54cf",
  triggering_user_name: "Alice Admin",
};

const createdEvent: GroupAutoCreatedEventType = {
  ...baseEvent,
  __typename: "GroupAutoCreatedEventType",
  event: "infrahub.group.auto_created",
  group_id: "18a2e83c-5415-e0f3-3399-c51c3c6f3398",
  group_name: "ops-admins",
  source_pattern: "^(?P<name>(ops|data)-.*)$",
  origin_value: "provider1",
};

const rejectedEvent: GroupAutoCreateRejectedEventType = {
  ...baseEvent,
  __typename: "GroupAutoCreateRejectedEventType",
  event: "infrahub.group.auto_create_rejected",
  rejected_claim_value: "pad-",
};

const cappedEvent: GroupAutoCreateCappedEventType = {
  ...baseEvent,
  __typename: "GroupAutoCreateCappedEventType",
  event: "infrahub.group.auto_create_capped",
  cap_value: 5,
  dropped_count: 7,
  dropped_claims: ["ops-extra-1", "ops-extra-2"],
};

describe("GroupAutoCreateEventTitle", () => {
  test("renders the created event with the group name and provider", async () => {
    // GIVEN / WHEN
    const component = await render(<GroupAutoCreateEventTitle {...createdEvent} />);

    // THEN
    await expect.element(component.getByText("ops-admins")).toBeVisible();
    await expect.element(component.getByText(/auto-created group/)).toBeVisible();
    await expect.element(component.getByText(/from provider1/)).toBeVisible();
  });

  test("renders the rejected event with the rejected claim", async () => {
    // GIVEN / WHEN
    const component = await render(<GroupAutoCreateEventTitle {...rejectedEvent} />);

    // THEN
    await expect.element(component.getByText("pad-")).toBeVisible();
    await expect.element(component.getByText(/rejected/)).toBeVisible();
  });

  test("renders the capped event with the cap and dropped count", async () => {
    // GIVEN / WHEN
    const component = await render(<GroupAutoCreateEventTitle {...cappedEvent} />);

    // THEN
    await expect.element(component.getByText("5")).toBeVisible();
    await expect.element(component.getByText(/dropping 7 claims/)).toBeVisible();
  });
});
