import { beforeEach, describe, expect, test, vi } from "vitest";

import { ObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import type { NodeObject } from "@/entities/nodes/types";
import { PERMISSION_ALLOW_ALL } from "@/entities/permission/constants";

import { render } from "../../../../../../../tests/components/render";
import { generateNodeSchema } from "../../../../../../../tests/fake/schema";
import { ObjectTableToolbar } from "./object-table-toolbar";

const schema = generateNodeSchema();

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
    const component = await render(
      <ObjectTableContext
        value={{
          filters: [],
          setFilters: vi.fn(),
          baseSchema: schema,
          selectedSchema: schema,
          permission: PERMISSION_ALLOW_ALL,
        }}
      >
        <ObjectTableToolbar selectedRows={mockNodeObjects} onClose={mockOnClose} />
      </ObjectTableContext>
    );

    // THEN
    await expect.element(component.getByRole("button", { name: "2 selected" })).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Add to groups" })).toBeVisible();
  });

  test("calls onClose when close button is clicked", async () => {
    // GIVEN
    const component = await render(
      <ObjectTableContext
        value={{
          filters: [],
          setFilters: vi.fn(),
          baseSchema: schema,
          selectedSchema: schema,
          permission: PERMISSION_ALLOW_ALL,
        }}
      >
        <ObjectTableToolbar selectedRows={mockNodeObjects} onClose={mockOnClose} />
      </ObjectTableContext>
    );

    // WHEN
    await component.getByRole("button", { name: "2 selected" }).click({ force: true });

    // THEN
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });
});
