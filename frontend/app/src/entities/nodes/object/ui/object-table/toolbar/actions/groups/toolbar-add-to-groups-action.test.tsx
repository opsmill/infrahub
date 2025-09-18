import { describe, expect, test, vi } from "vitest";

import { store } from "@/shared/stores";

import { getRelationships } from "@/entities/nodes/relationships/domain/get-relationships/get-relationships";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import type { NodeObject } from "@/entities/nodes/types";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../../../../tests/components/render";
import { generateNodeSchema } from "../../../../../../../../../tests/fake/schema";
import { ToolbarAddToGroupsAction } from "./toolbar-add-to-groups-action";

vi.mock("@/entities/nodes/relationships/domain/get-relationships/get-relationships");

describe("ToolbarAddToGroupsAction Component", () => {
  const mockSelectedRows = [
    { id: "obj-1", display_label: "Object 1", __typename: "TestType" },
    { id: "obj-2", display_label: "Object 2", __typename: "TestType" },
  ] as NodeObject[];

  const mockGroups: RelationshipNode[] = [
    { id: "group-1", display_label: "Test Group 1", __typename: "CoreGroup" },
    { id: "group-2", display_label: "Test Group 2", __typename: "CoreGroup" },
  ];

  const groupSchema = generateNodeSchema({ kind: "CoreGroup" });

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getRelationships).mockResolvedValue(mockGroups);
    store.set(nodeSchemasAtom, [groupSchema]);
  });

  test("opens the popover when clicking the button", async () => {
    // GIVEN
    const component = render(<ToolbarAddToGroupsAction selectedRows={mockSelectedRows} />);

    // WHEN
    await component.getByRole("button", { name: "Add to groups" }).click();

    // THEN
    await expect.element(component.getByRole("dialog", { name: "Add to groups" })).toBeVisible();
    await expect.element(component.getByPlaceholder("Filter...")).toBeVisible();
    await expect.element(component.getByRole("option", { name: "Test Group 1" })).toBeVisible();
    await expect.element(component.getByRole("option", { name: "Test Group 2" })).toBeVisible();
  });
});
