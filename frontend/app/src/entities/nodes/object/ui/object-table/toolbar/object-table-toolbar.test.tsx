import { NodeObject } from "@/entities/nodes/types";
import { describe, expect, test, vi } from "vitest";
import { render } from "../../../../../../../tests/components/render";
import { ObjectTableToolbar } from "./object-table-toolbar";

describe("ObjectTableToolbar Component", () => {
  const mockNodeObjects = [
    { id: "obj-1", display_label: "Object 1", __typename: "TestType" },
    { id: "obj-2", display_label: "Object 2", __typename: "TestType" },
  ] as NodeObject[];

  const mockOnClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("renders correctly with selected rows", async () => {
    // GIVEN
    const component = render(
      <ObjectTableToolbar selectedRows={mockNodeObjects} onClose={mockOnClose} />
    );

    // THEN
    await expect.element(component.getByText("2 selected")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Add to groups" })).toBeVisible();
  });

  test("calls onClose when close button is clicked", async () => {
    // GIVEN
    const component = render(
      <ObjectTableToolbar selectedRows={mockNodeObjects} onClose={mockOnClose} />
    );

    // WHEN
    await component.getByText("2 selected").click();

    // THEN
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });
});
