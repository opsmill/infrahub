import { useAddRelationships } from "@/entities/nodes/relationships/domain/add-relationships/add-relationships.mutation";
import { getRelationships } from "@/entities/nodes/relationships/domain/get-relationships/get-relationships";
import { useRemoveRelationships } from "@/entities/nodes/relationships/domain/remove-relationships/remove-relationships.mutation";
import { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { NodeObject } from "@/entities/nodes/types";
import { describe, expect, test, vi } from "vitest";
import { render } from "../../../../../../../tests/components/render";
import { ToolbarAddToGroupsAction } from "./toolbar-add-to-groups-action";

// Mock the mutations and getRelationships
vi.mock("@/entities/nodes/relationships/domain/add-relationships/add-relationships.mutation");
vi.mock("@/entities/nodes/relationships/domain/remove-relationships/remove-relationships.mutation");
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

  beforeEach(() => {
    vi.clearAllMocks();

    // Setup default mocks for the hooks
    vi.mocked(useAddRelationships).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as any);

    vi.mocked(useRemoveRelationships).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as any);

    // Mock getRelationships to return test groups
    vi.mocked(getRelationships).mockResolvedValue(mockGroups);
  });

  test("opens the popover when clicking the button", async () => {
    // GIVEN
    const component = render(<ToolbarAddToGroupsAction selectedRows={mockSelectedRows} />);

    // WHEN
    await component.getByRole("button", { name: "Add to groups" }).click();

    // THEN
    // The combobox should be visible in the popover
    await expect.element(component.getByRole("dialog", { name: "Add to groups" })).toBeVisible();
    await expect.element(component.getByPlaceholder("Filter...")).toBeVisible();
    await expect.element(component.getByRole("option", { name: "Test Group 1" })).toBeVisible();
    await expect.element(component.getByRole("option", { name: "Test Group 2" })).toBeVisible();
  });

  test("adds relationships when a group is selected", async () => {
    // GIVEN
    const mockAddRelationships = vi.fn();
    vi.mocked(useAddRelationships).mockReturnValue({
      mutate: mockAddRelationships,
      isPending: true,
    } as any);

    const component = render(<ToolbarAddToGroupsAction selectedRows={mockSelectedRows} />);

    // WHEN
    await component.getByRole("button", { name: "Add to groups" }).click();
    await component.getByRole("option", { name: "Test Group 1" }).click();

    // THEN
    expect(mockAddRelationships).toHaveBeenCalledWith({
      objectId: "group-1",
      relationshipName: "members",
      relationshipIds: ["obj-1", "obj-2"],
    });
    await expect.element(component.getByRole("status")).toBeVisible();
  });

  test("removes a group when clicking the remove button", async () => {
    // GIVEN
    const mockRemoveRelationships = vi.fn();
    vi.mocked(useRemoveRelationships).mockReturnValue({
      mutate: mockRemoveRelationships,
      isPending: false,
    } as any);

    const component = render(<ToolbarAddToGroupsAction selectedRows={mockSelectedRows} />);

    // WHEN
    await component.getByRole("button", { name: "Add to groups" }).click();
    await component.getByRole("option", { name: "Test Group 1" }).click(); // Select the first group
    await component.getByRole("button", { name: "Remove from group" }).click(); // Then remove it

    // THEN
    expect(mockRemoveRelationships).toHaveBeenCalledWith(
      {
        objectId: "group-1",
        relationshipName: "members",
        relationshipIds: ["obj-1", "obj-2"],
      },
      expect.objectContaining({
        onSuccess: expect.any(Function),
      })
    );
  });

  test("filters out already selected groups", async () => {
    // GIVEN
    const component = render(<ToolbarAddToGroupsAction selectedRows={mockSelectedRows} />);

    // WHEN
    await component.getByRole("button", { name: "Add to groups" }).click();
    await component.getByRole("option", { name: "Test Group 1" }).click();

    // THEN
    await expect.element(component.getByRole("option", { name: "Test Group 2" })).toBeVisible();
    await expect
      .poll(() => component.getByRole("option", { name: "Test Group 1" }).query())
      .toBeNull();
  });
});
