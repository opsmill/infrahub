import { afterEach, describe, expect, test } from "vitest";

import type { NodeMutatedEvent } from "@/shared/api/graphql/generated/types";

import type { ProposedChangeEvent } from "@/entities/events/domain/model/event";

import { render } from "../../../../tests/components/render";
import { EventCard } from "./event-card";

const initialUrl = window.location.pathname + window.location.search;

const updatedEvent: NodeMutatedEvent = {
  id: "7dfb5bf2-d0ad-4a06-bfd3-d0916b5b904e",
  __typename: "NodeMutatedEvent",
  event: "infrahub.node.updated",
  branch: "main",
  occurred_at: "2026-04-06T21:29:30.290070+00:00",
  level: 0,
  account_id: null,
  primary_node: {
    id: "18a2e83c-5415-e0f3-3399-c51c3c6f3398",
    kind: "InfraDevice",
    __typename: "RelatedNode",
  },
  related_nodes: [],
  has_children: false,
  parent_id: null,
  payload: { data: { node_kind: "InfraDevice", changelog: { display_label: "atl1-edge1" } } },
  attributes: [
    {
      __typename: "InfrahubMutatedAttribute",
      action: "UPDATED",
      kind: "Text",
      name: "description",
      value: "Edge router",
      value_previous: "Spare router",
    },
  ],
  relationships: [],
};

describe("EventCard", () => {
  afterEach(() => {
    window.history.replaceState(null, "", initialUrl);
  });

  test("shows the changed attributes of a node event under its title outside the homepage", async () => {
    // GIVEN
    window.history.replaceState(
      null,
      "",
      "/objects/InfraDevice/18a2e83c-5415-e0f3-3399-c51c3c6f3398"
    );

    // WHEN
    const component = await render(<EventCard {...updatedEvent} />);

    // THEN
    await expect.element(component.getByRole("link", { name: "atl1-edge1" })).toBeVisible();
    await expect.element(component.getByText("description")).toBeVisible();
    await expect.element(component.getByText("Edge router")).toBeVisible();
  });

  test("hides the changed attributes of a node event on the homepage", async () => {
    // GIVEN
    window.history.replaceState(null, "", "/");

    // WHEN
    const component = await render(<EventCard {...updatedEvent} />);

    // THEN
    await expect.element(component.getByRole("link", { name: "atl1-edge1" })).toBeVisible();
    await expect.element(component.getByText("description")).not.toBeInTheDocument();
  });

  test("shows the review action of a proposed change review event", async () => {
    // GIVEN
    const event: ProposedChangeEvent = {
      id: "18a3c089-085a-ac67-38d1-c5139dd74202",
      __typename: "ProposedChangeReviewEvent",
      event: "infrahub.proposed_change.approved",
      branch: "main",
      occurred_at: "2026-04-06T21:29:30.290070+00:00",
      level: 0,
      account_id: null,
      primary_node: null,
      related_nodes: [],
      has_children: false,
    };

    // WHEN
    const component = await render(<EventCard {...event} />);

    // THEN
    await expect.element(component.getByText("approved the proposed change")).toBeVisible();
    await expect
      .element(component.getByText("infrahub.proposed_change.approved"))
      .not.toBeInTheDocument();
  });
});
