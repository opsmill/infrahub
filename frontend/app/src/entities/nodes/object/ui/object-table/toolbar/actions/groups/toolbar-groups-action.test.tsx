import type React from "react";
import {
  afterAll,
  afterEach,
  beforeEach,
  describe,
  expect,
  onTestFinished,
  test,
  vi,
} from "vitest";
import { userEvent } from "vitest/browser";

import { queryClient } from "@/shared/api/rest/client";
import { store } from "@/shared/stores";

import { OBJECT_COLUMN_SURFACE } from "@/entities/nodes/columns/domain/rules/column-surfaces";
import type { NodeObject } from "@/entities/nodes/object/domain/model/node";
import { ObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/model/relationships";
import { addRelationships } from "@/entities/nodes/relationships/domain/use-cases/add-relationships";
import { getRelationships } from "@/entities/nodes/relationships/domain/use-cases/get-relationships";
import { removeRelationships } from "@/entities/nodes/relationships/domain/use-cases/remove-relationships";
import {
  PERMISSION_ALLOW_ALL,
  type Permission,
} from "@/entities/permission/domain/model/permission";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../../../../tests/components/render";
import { initPointerTracking } from "../../../../../../../../../tests/components/utils";
import { generateBranch } from "../../../../../../../../../tests/fake/branch";
import { generatePermission } from "../../../../../../../../../tests/fake/permission";
import { generateNodeSchema } from "../../../../../../../../../tests/fake/schema";
import { ToolbarAddToGroupsAction } from "./toolbar-add-to-groups-action";
import { ToolbarGroupsAction, type ToolbarGroupsActionProps } from "./toolbar-groups-action";
import { ToolbarRemoveFromGroupsAction } from "./toolbar-remove-from-groups-action";

vi.mock("@/entities/nodes/relationships/domain/use-cases/get-relationships");
vi.mock("@/entities/nodes/relationships/domain/use-cases/add-relationships");
vi.mock("@/entities/nodes/relationships/domain/use-cases/remove-relationships");

const schema = generateNodeSchema();
const groupSchema = generateNodeSchema({ kind: "CoreGroup" });
const updateDenied = generatePermission({ update: false });

const selectedRows = [
  { id: "obj-1", display_label: "Object 1", __typename: "TestType" },
  { id: "obj-2", display_label: "Object 2", __typename: "TestType" },
] as NodeObject[];

const groups: RelationshipNode[] = [
  { id: "group-1", display_label: "Test Group 1", __typename: "CoreGroup" },
  { id: "group-2", display_label: "Test Group 2", __typename: "CoreGroup" },
];

const renderInObjectTable = (action: React.ReactElement, permission: Permission) =>
  render(
    <ObjectTableContext
      value={{
        filters: [],
        setFilters: vi.fn(),
        baseSchema: schema,
        selectedSchema: schema,
        permission,
        columnSurface: OBJECT_COLUMN_SURFACE,
        supportsColumnVisibility: false,
      }}
    >
      {/* The padding keeps the pointer parking corner off the button so its tooltip closes. */}
      <div className="p-4">{action}</div>
    </ObjectTableContext>
  );

const renderGroupsAction = (
  props: Partial<ToolbarGroupsActionProps> = {},
  permission: Permission = PERMISSION_ALLOW_ALL
) =>
  renderInObjectTable(
    <ToolbarGroupsAction
      selectedRows={selectedRows}
      label="Tag groups"
      variant="outline"
      mutateMembers={vi.fn().mockResolvedValue(undefined)}
      groupsQueryFilter={{ group_type__values: ["default"] }}
      {...props}
    />,
    permission
  );

describe("ToolbarGroupsAction", () => {
  const initialNodeSchemas = store.get(nodeSchemasAtom);

  beforeEach(() => {
    queryClient.clear();
    vi.mocked(getRelationships).mockResolvedValue(groups);
    vi.mocked(addRelationships).mockResolvedValue(undefined);
    vi.mocked(removeRelationships).mockResolvedValue(undefined);
    store.set(nodeSchemasAtom, [groupSchema]);
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  afterAll(() => {
    store.set(nodeSchemasAtom, initialNodeSchemas);
  });

  test.each([
    {
      variant: "outline",
      colorClass: "text-foreground",
      access: "allowed",
      permission: PERMISSION_ALLOW_ALL,
    },
    {
      variant: "outline",
      colorClass: "text-foreground",
      access: "denied",
      permission: updateDenied,
    },
    {
      variant: "danger-outline",
      colorClass: "text-danger",
      access: "allowed",
      permission: PERMISSION_ALLOW_ALL,
    },
    {
      variant: "danger-outline",
      colorClass: "text-danger",
      access: "denied",
      permission: updateDenied,
    },
  ] as const)(
    "renders the $variant button when updates are $access",
    async ({ variant, colorClass, permission }) => {
      // GIVEN
      const props = { label: "Tag groups", variant };

      // WHEN
      const component = await renderGroupsAction(props, permission);

      // THEN
      await expect
        .element(component.getByRole("button", { name: "Tag groups" }))
        .toHaveClass(colorClass);
    }
  );

  test("disables the button and shows the permission message when updates are denied", async () => {
    // GIVEN
    const component = await renderGroupsAction({}, updateDenied);
    onTestFinished(() => initPointerTracking(component.locator));
    await initPointerTracking(component.locator);

    // WHEN
    await component.getByRole("button", { name: "Tag groups" }).hover();

    // THEN
    await expect.element(component.getByRole("button", { name: "Tag groups" })).toBeDisabled();
    await expect
      .element(component.getByRole("tooltip", { name: "Update not allowed" }))
      .toBeVisible();
  });

  test("keeps the denied button reachable with the keyboard without opening the dialog", async () => {
    // GIVEN
    const component = await renderGroupsAction({}, updateDenied);

    // WHEN
    await userEvent.tab();
    await userEvent.keyboard("{Enter}");

    // THEN
    await expect.element(component.getByRole("button", { name: "Tag groups" })).toHaveFocus();
    await expect.element(component.getByRole("dialog")).not.toBeInTheDocument();
  });

  test("opens a dialog named after the label that lists the groups matching the filter", async () => {
    // GIVEN
    const groupsQueryFilter = { members__ids: ["obj-1", "obj-2"] };
    const component = await renderGroupsAction({ groupsQueryFilter });

    // WHEN
    await component.getByRole("button", { name: "Tag groups" }).click();

    // THEN
    await expect.element(component.getByRole("dialog", { name: "Tag groups" })).toBeVisible();
    await expect.element(component.getByRole("option", { name: "Test Group 1" })).toBeVisible();
    expect(getRelationships).toHaveBeenCalledWith(
      expect.objectContaining({ peer: "CoreGroup", filterQuery: groupsQueryFilter })
    );
  });

  test("updates the members of each chosen group with the selected rows on the current branch", async () => {
    // GIVEN
    const mutateMembers = vi.fn().mockResolvedValue(undefined);
    const component = await renderGroupsAction({ mutateMembers });
    await component.getByRole("button", { name: "Tag groups" }).click();
    await component.getByRole("option", { name: "Test Group 1" }).click();
    await component.getByRole("option", { name: "Test Group 2" }).click();

    // WHEN
    await component.getByRole("button", { name: "Validate" }).click();

    // THEN
    await expect.poll(() => mutateMembers).toHaveBeenCalledTimes(2);
    const branchName = generateBranch().name;
    expect(mutateMembers).toHaveBeenCalledWith({
      objectId: "group-1",
      relationshipName: "members",
      relationshipIds: ["obj-1", "obj-2"],
      branchName,
    });
    expect(mutateMembers).toHaveBeenCalledWith({
      objectId: "group-2",
      relationshipName: "members",
      relationshipIds: ["obj-1", "obj-2"],
      branchName,
    });
  });

  test("refreshes the object queries after the group update succeeds", async () => {
    // GIVEN
    const invalidateQueries = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockResolvedValue(undefined);
    onTestFinished(() => invalidateQueries.mockRestore());
    const mutateMembers = vi.fn().mockResolvedValue(undefined);
    const component = await renderGroupsAction({ mutateMembers });
    await component.getByRole("button", { name: "Tag groups" }).click();
    await component.getByRole("option", { name: "Test Group 1" }).click();

    // WHEN
    await component.getByRole("button", { name: "Validate" }).click();

    // THEN
    await expect
      .poll(() => invalidateQueries)
      .toHaveBeenCalledExactlyOnceWith({ queryKey: objectQueryKeys.all });
    expect(mutateMembers).toHaveBeenCalledBefore(invalidateQueries);
  });

  test("closes the dialog from the result panel", async () => {
    // GIVEN
    const component = await renderGroupsAction();
    await component.getByRole("button", { name: "Tag groups" }).click();
    await component.getByRole("option", { name: "Test Group 1" }).click();
    await component.getByRole("button", { name: "Validate" }).click();
    await expect
      .element(component.getByRole("heading", { name: "1 / 1 group updated successfully" }))
      .toBeVisible();

    // WHEN
    await component.getByRole("button", { name: "Close" }).click();

    // THEN
    await expect.element(component.getByRole("dialog")).not.toBeInTheDocument();
  });

  test.each([
    {
      label: "Add to groups",
      Action: ToolbarAddToGroupsAction,
      groupsQueryFilter: { group_type__values: ["default"] },
    },
    {
      label: "Remove from groups",
      Action: ToolbarRemoveFromGroupsAction,
      groupsQueryFilter: { members__ids: ["obj-1", "obj-2"] },
    },
  ])(
    "$label opens a dialog that lists only the groups it applies to",
    async ({ label, Action, groupsQueryFilter }) => {
      // GIVEN
      const component = await renderInObjectTable(
        <Action selectedRows={selectedRows} />,
        PERMISSION_ALLOW_ALL
      );

      // WHEN
      await component.getByRole("button", { name: label }).click();

      // THEN
      await expect.element(component.getByRole("dialog", { name: label })).toBeVisible();
      await expect.element(component.getByRole("option", { name: "Test Group 1" })).toBeVisible();
      expect(getRelationships).toHaveBeenCalledWith(
        expect.objectContaining({ peer: "CoreGroup", filterQuery: groupsQueryFilter })
      );
    }
  );

  test.each([
    {
      label: "Add to groups",
      Action: ToolbarAddToGroupsAction,
      useCase: addRelationships,
      otherUseCase: removeRelationships,
    },
    {
      label: "Remove from groups",
      Action: ToolbarRemoveFromGroupsAction,
      useCase: removeRelationships,
      otherUseCase: addRelationships,
    },
  ])(
    "$label updates the group members through its own use case",
    async ({ label, Action, useCase, otherUseCase }) => {
      // GIVEN
      const component = await renderInObjectTable(
        <Action selectedRows={selectedRows} />,
        PERMISSION_ALLOW_ALL
      );
      await component.getByRole("button", { name: label }).click();
      await component.getByRole("option", { name: "Test Group 1" }).click();

      // WHEN
      await component.getByRole("button", { name: "Validate" }).click();

      // THEN
      await expect
        .poll(() => useCase)
        .toHaveBeenCalledExactlyOnceWith({
          objectId: "group-1",
          relationshipName: "members",
          relationshipIds: ["obj-1", "obj-2"],
          branchName: generateBranch().name,
        });
      expect(otherUseCase).not.toHaveBeenCalled();
    }
  );

  test.each([
    { label: "Add to groups", Action: ToolbarAddToGroupsAction },
    { label: "Remove from groups", Action: ToolbarRemoveFromGroupsAction },
  ])("$label is disabled when updates are denied", async ({ label, Action }) => {
    // GIVEN
    const permission = updateDenied;

    // WHEN
    const component = await renderInObjectTable(<Action selectedRows={selectedRows} />, permission);

    // THEN
    await expect.element(component.getByRole("button", { name: label })).toBeDisabled();
  });
});
