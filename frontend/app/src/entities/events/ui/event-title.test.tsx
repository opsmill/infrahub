import type React from "react";
import { afterEach, describe, expect, test, vi } from "vitest";

import type {
  AccountLoggedInEventType,
  AccountLoggedOutEventType,
  BranchMergedEvent,
  GroupAutoCreatedEventType,
  NodeMutatedEvent,
  ProposedChangeReviewEvent,
  ProposedChangeThreadEvent,
  StandardEvent,
} from "@/shared/api/graphql/generated/types";

import type { EventType } from "@/entities/events/domain/model/event";

import { render } from "../../../../tests/components/render";
import { EventCard } from "./event-card";
import { EventTitle } from "./event-title";
import { Event } from "./global-event";

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
};

const approvedEvent: ProposedChangeReviewEvent = {
  ...baseEvent,
  __typename: "ProposedChangeReviewEvent",
  event: "infrahub.proposed_change.approved",
  reviewer_account_id: "18a2e83c-0e80-fa90-3392-c51809fb54cf",
  reviewer_account_name: "jbauer",
  reviewer_decision: "APPROVE",
};

describe("EventTitle", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("shows the review action for a proposed change review event", async () => {
    // GIVEN
    const event = approvedEvent;

    // WHEN
    const component = await render(<EventTitle event={event} />);

    // THEN
    await expect.element(component.getByText("approved the proposed change")).toBeVisible();
    await expect
      .element(component.getByText("infrahub.proposed_change.approved"))
      .not.toBeInTheDocument();
  });

  test("shows the proposed change title for a standard event that carries a proposed change name", async () => {
    // GIVEN
    const event: StandardEvent = {
      ...baseEvent,
      __typename: "StandardEvent",
      event: "infrahub.proposed_change.rejected",
    };

    // WHEN
    const component = await render(<EventTitle event={event} />);

    // THEN
    await expect.element(component.getByText("rejected the proposed change")).toBeVisible();
  });

  test("shows the branch title for a branch merge, whose name is also a proposed change event", async () => {
    // GIVEN
    const event: BranchMergedEvent = {
      ...baseEvent,
      __typename: "BranchMergedEvent",
      event: "infrahub.branch.merged",
      source_branch: "feature-1",
    };

    // WHEN
    const component = await render(<EventTitle event={event} />);

    // THEN
    await expect.element(component.getByText("merged the branch")).toBeVisible();
    await expect.element(component.getByText("feature-1")).toBeVisible();
  });

  test("shows the object label for a node event", async () => {
    // GIVEN
    const event: NodeMutatedEvent = {
      ...baseEvent,
      __typename: "NodeMutatedEvent",
      event: "infrahub.node.created",
      primary_node: {
        id: "18a2e83c-5415-e0f3-3399-c51c3c6f3398",
        kind: "InfraDevice",
        __typename: "RelatedNode",
      },
      payload: { data: { node_kind: "InfraDevice", changelog: { display_label: "atl1-edge1" } } },
      attributes: [],
      relationships: [],
    };

    // WHEN
    const component = await render(<EventTitle event={event} />);

    // THEN
    await expect.element(component.getByText("created", { exact: true })).toBeVisible();
    await expect.element(component.getByRole("link", { name: "atl1-edge1" })).toBeVisible();
  });

  test("shows the authentication method for an account login", async () => {
    // GIVEN
    const event: AccountLoggedInEventType = {
      ...baseEvent,
      __typename: "AccountLoggedInEventType",
      event: "infrahub.account.logged_in",
      account_name: "jbauer",
      account_type: "User",
      auth_method: "password",
      client_ip: null,
      groups: [],
      identity_source: null,
      kind: "CoreAccount",
      roles: [],
      session_id: "18a3e1d1-efbe-bd53-38db-c51848891c21",
      timestamp: "2026-04-06T21:29:30.290003+00:00",
      user_agent: null,
    };

    // WHEN
    const component = await render(<EventTitle event={event} />);

    // THEN
    await expect.element(component.getByText("logged in via password")).toBeVisible();
  });

  test("shows the logout for an account logout", async () => {
    // GIVEN
    const event: AccountLoggedOutEventType = {
      ...baseEvent,
      __typename: "AccountLoggedOutEventType",
      event: "infrahub.account.logged_out",
      account_name: "admin",
      client_ip: null,
      kind: "CoreAccount",
      logout_type: "user_initiated",
      session_id: "18a3c089-085a-ac67-38d1-c5139dd74202",
      timestamp: "2026-04-06T11:19:42.702056+00:00",
      user_agent: null,
    };

    // WHEN
    const component = await render(<EventTitle event={event} />);

    // THEN
    await expect.element(component.getByText("logged out")).toBeVisible();
  });

  test("shows the created group for a group auto-creation", async () => {
    // GIVEN
    const event: GroupAutoCreatedEventType = {
      ...baseEvent,
      __typename: "GroupAutoCreatedEventType",
      event: "infrahub.group.auto_created",
      idp: "provider1",
      protocol: "oidc",
      triggering_user_id: "18a2e83c-0e80-fa90-3392-c51809fb54cf",
      triggering_user_name: "Alice Admin",
      group_id: "18a2e83c-5415-e0f3-3399-c51c3c6f3398",
      group_name: "ops-admins",
      source_pattern: "^(?P<name>(ops|data)-.*)$",
      origin_value: "provider1",
    };

    // WHEN
    const component = await render(<EventTitle event={event} />);

    // THEN
    await expect.element(component.getByText(/auto-created group/)).toBeVisible();
    await expect.element(component.getByText("ops-admins")).toBeVisible();
  });

  test("shows the event name without a warning for a proposed change event that has no title", async () => {
    // GIVEN
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const event: ProposedChangeThreadEvent = {
      ...baseEvent,
      __typename: "ProposedChangeThreadEvent",
      event: "infrahub.proposed_change_thread.updated",
    };

    // WHEN
    const component = await render(<EventTitle event={event} />);

    // THEN
    await expect
      .element(component.getByText("infrahub.proposed_change_thread.updated"))
      .toBeVisible();
    expect(warn).not.toHaveBeenCalledWith(expect.stringContaining("unexpected type"));
  });

  test("shows the event name and warns for an event type it does not know", async () => {
    // GIVEN
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const event = {
      ...baseEvent,
      __typename: "FutureEvent",
      event: "infrahub.future.happened",
    } as unknown as EventType;

    // WHEN
    const component = await render(<EventTitle event={event} />);

    // THEN
    await expect.element(component.getByText("infrahub.future.happened")).toBeVisible();
    expect(warn).toHaveBeenCalledWith(expect.stringContaining("unexpected type"));
  });

  test.each<[string, (props: EventType) => React.ReactElement]>([
    ["activity card", (props) => <EventCard {...props} />],
    ["Activities list row", (props) => <Event {...props} />],
  ])("shows the proposed change review action in the %s", async (_, renderCaller) => {
    // GIVEN
    const event = approvedEvent;

    // WHEN
    const component = await render(renderCaller(event));

    // THEN
    await expect.element(component.getByText("approved the proposed change")).toBeVisible();
    await expect
      .element(component.getByText("infrahub.proposed_change.approved"))
      .not.toBeInTheDocument();
  });
});
