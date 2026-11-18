import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { ProposedChangeEvent } from "@/entities/events/domain/model/event";
import { PERMISSION_ALLOW_ALL } from "@/entities/permission/domain/model/permission";
import { useGetObjectPermissions } from "@/entities/permission/ui/queries/get-object-permissions.query";
import { useGetProposedChangeThread } from "@/entities/proposed-changes/ui/queries/get-proposed-change-thread.query";

import { render } from "../../../../tests/components/render";
import { Event } from "./global-event";

vi.mock("@/entities/proposed-changes/ui/queries/get-proposed-change-thread.query");
vi.mock("@/entities/permission/ui/queries/get-object-permissions.query", () => ({
  useGetObjectPermissions: vi.fn(),
}));

const threadId = "18a3e1d1-efbe-bd53-38db-c51848891c21";

const commonEvent = {
  id: "7dfb5bf2-d0ad-4a06-bfd3-d0916b5b904e",
  branch: "main",
  occurred_at: "2026-04-06T21:29:30.290070+00:00",
  level: 0,
  account_id: null,
  primary_node: null,
  related_nodes: [],
  has_children: false,
};

describe("Event", () => {
  beforeEach(() => {
    vi.mocked(useGetObjectPermissions).mockReturnValue({
      data: PERMISSION_ALLOW_ALL,
      isPending: false,
    } as unknown as ReturnType<typeof useGetObjectPermissions>);
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  test("shows the review action of a proposed change review event", async () => {
    // GIVEN
    const event: ProposedChangeEvent = {
      ...commonEvent,
      __typename: "ProposedChangeReviewEvent",
      event: "infrahub.proposed_change.approved",
    };

    // WHEN
    const component = await render(<Event {...event} />);

    // THEN
    await expect.element(component.getByText("approved the proposed change")).toBeVisible();
    await expect
      .element(component.getByText("infrahub.proposed_change.approved"))
      .not.toBeInTheDocument();
  });

  test("shows the created thread with its comments for a thread creation", async () => {
    // GIVEN
    vi.mocked(useGetProposedChangeThread).mockReturnValue({
      data: {
        id: threadId,
        __typename: "CoreObjectThread",
        display_label: "Thread",
        label: { value: null },
        resolved: { value: false },
        object_path: { value: "data/18a2e83c-5415-e0f3-3399-c51c3c6f3398" },
        comments: {
          count: 1,
          edges: [
            {
              node_metadata: {
                created_at: "2026-04-06T21:29:30.290070+00:00",
                created_by: { display_label: "Admin" },
              },
              node: {
                id: "18a3e1d2-0a4c-3d8e-38db-c518a1b2c3d4",
                display_label: "Check the description",
                text: { value: "Check the description" },
              },
            },
          ],
        },
      },
      isPending: false,
      error: null,
    } as unknown as ReturnType<typeof useGetProposedChangeThread>);
    const event: ProposedChangeEvent = {
      ...commonEvent,
      __typename: "ProposedChangeThreadEvent",
      event: "infrahub.proposed_change_thread.created",
      related_nodes: [{ id: threadId, kind: "CoreObjectThread", __typename: "RelatedNode" }],
    };

    // WHEN
    const component = await render(<Event {...event} />);

    // THEN
    await expect.element(component.getByText("created a thread")).toBeVisible();
    await expect.element(component.getByText("Check the description")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Reply" })).toBeVisible();
    expect(useGetProposedChangeThread).toHaveBeenCalledWith({ threadId });
  });
});
