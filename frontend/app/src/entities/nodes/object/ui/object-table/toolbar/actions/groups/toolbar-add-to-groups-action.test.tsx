import { beforeEach, describe, expect, test, vi } from "vitest";

import { queryClient } from "@/shared/api/rest/client";
import { store } from "@/shared/stores";

import { ObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { getRelationships } from "@/entities/nodes/relationships/domain/get-relationships/get-relationships";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import type { NodeObject } from "@/entities/nodes/types";
import { PERMISSION_ALLOW_ALL } from "@/entities/permission/constants";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../../../../tests/components/render";
import { generateNodeSchema } from "../../../../../../../../../tests/fake/schema";
import { ToolbarAddToGroupsAction } from "./toolbar-add-to-groups-action";

vi.mock("@/entities/nodes/relationships/domain/get-relationships/get-relationships");

const schema = generateNodeSchema();

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
    queryClient.clear();
    vi.clearAllMocks();
    vi.mocked(getRelationships).mockResolvedValue(mockGroups);
    store.set(nodeSchemasAtom, [groupSchema]);
  });

  test("opens the popover when clicking the button", async () => {
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
        <ToolbarAddToGroupsAction selectedRows={mockSelectedRows} />
      </ObjectTableContext>
    );

    // WHEN
    await component.getByRole("button", { name: "Add to groups" }).click();

    // THEN
    await expect.element(component.getByRole("dialog", { name: "Add to groups" })).toBeVisible();
    await expect.element(component.getByPlaceholder("Search by name or UUID...")).toBeVisible();
    await expect.element(component.getByRole("option", { name: "Test Group 1" })).toBeVisible();
    await expect.element(component.getByRole("option", { name: "Test Group 2" })).toBeVisible();
  });

  test("hides internal groups from the add-to-groups dropdown", async () => {
    // GIVEN: a default user-assignable group and an internal system-managed group exist;
    // the API filters by group_type when the caller asks for it
    const userGroup: RelationshipNode = {
      id: "group-default",
      display_label: "User Group",
      __typename: "CoreGroup",
    };
    const internalGroup: RelationshipNode = {
      id: "group-internal",
      display_label: "Internal Group",
      __typename: "CoreGroup",
    };
    vi.mocked(getRelationships).mockImplementation(async (params) => {
      const requestedTypes = params?.filterQuery?.group_type__values as string[] | undefined;
      if (requestedTypes && !requestedTypes.includes("internal")) {
        return [userGroup];
      }
      return [userGroup, internalGroup];
    });

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
        <ToolbarAddToGroupsAction selectedRows={mockSelectedRows} />
      </ObjectTableContext>
    );

    // WHEN
    await component.getByRole("button", { name: "Add to groups" }).click();

    // THEN
    await expect.element(component.getByRole("option", { name: "User Group" })).toBeVisible();
    await expect
      .poll(() =>
        component
          .getByTestId("group-selector")
          .getByRole("option", { name: "Internal Group" })
          .query()
      )
      .toBeNull();
  });
});
