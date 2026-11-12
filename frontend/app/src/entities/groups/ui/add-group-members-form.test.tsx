import { Sheet } from "@infrahub/ui";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { userEvent } from "vitest/browser";

import { queryClient } from "@/shared/api/rest/client";
import { store } from "@/shared/stores";

import { AddGroupMembersForm } from "@/entities/groups/ui/add-group-members-form";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/model/relationships";
import { addRelationships } from "@/entities/nodes/relationships/domain/use-cases/add-relationships";
import { getRelationships } from "@/entities/nodes/relationships/domain/use-cases/get-relationships";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../tests/components/render";
import {
  generateGenericSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../tests/fake/schema";

vi.mock("@/entities/nodes/relationships/domain/use-cases/get-relationships");
vi.mock("@/entities/nodes/relationships/domain/use-cases/add-relationships");

describe("AddGroupMembersForm", () => {
  const anyNodeGeneric = generateGenericSchema({
    kind: "CoreNode",
    name: "Node",
    label: "Node",
    relationships: [],
    used_by: ["TestDevice", "TestTag"],
  });
  const deviceSchema = generateNodeSchema({ kind: "TestDevice", name: "Device", label: "Device" });
  const tagSchema = generateNodeSchema({ kind: "TestTag", name: "Tag", label: "Tag" });

  const membersRelationship = generateRelationshipSchema({
    name: "members",
    label: "Members",
    peer: "CoreNode",
    kind: "Generic",
    cardinality: "many",
  });

  const devices: RelationshipNode[] = [
    { id: "device-1", display_label: "atl1-edge", __typename: "TestDevice" },
    { id: "device-2", display_label: "atl1-core", __typename: "TestDevice" },
  ];

  beforeEach(() => {
    queryClient.clear();
    vi.mocked(addRelationships).mockReset();
    store.set(nodeSchemasAtom, [deviceSchema, tagSchema]);
    store.set(genericSchemasAtom, [anyNodeGeneric]);
    vi.mocked(getRelationships).mockImplementation(async ({ peer }) =>
      peer === "TestDevice" ? devices : []
    );
  });

  test("adds every selected node to the group in one request", async () => {
    const onSuccess = vi.fn();
    const component = await render(
      <AddGroupMembersForm
        groupId="group-1"
        membersRelationship={membersRelationship}
        onSuccess={onSuccess}
        onCancel={() => {}}
      />
    );

    await component.getByRole("combobox", { name: "Kind" }).click();
    await component.getByRole("option", { name: /Device/ }).click();
    await component.getByLabelText("Device", { exact: true }).click();
    await component.getByRole("option", { name: "atl1-edge" }).click();
    await component.getByRole("option", { name: "atl1-core" }).click();
    await userEvent.keyboard("{Escape}");
    await component.getByRole("button", { name: "Save" }).click();

    await expect.poll(() => onSuccess).toHaveBeenCalledOnce();
    expect(addRelationships).toHaveBeenCalledOnce();
    expect(vi.mocked(addRelationships).mock.calls[0]?.[0]).toMatchObject({
      objectId: "group-1",
      relationshipName: "members",
      relationshipIds: ["device-1", "device-2"],
    });
    await expect.element(component.getByText("2 members added")).toBeVisible();
  });

  test("closes the member list with Escape and keeps the drawer open", async () => {
    const onOpenChange = vi.fn();
    const component = await render(
      <Sheet isOpen onOpenChange={onOpenChange}>
        <AddGroupMembersForm
          groupId="group-1"
          membersRelationship={membersRelationship}
          onSuccess={() => {}}
          onCancel={() => {}}
        />
      </Sheet>
    );

    await component.getByRole("combobox", { name: "Kind" }).click();
    await component.getByRole("option", { name: /Device/ }).click();
    await component.getByLabelText("Device", { exact: true }).click();
    await component.getByRole("option", { name: "atl1-edge" }).click();
    await userEvent.keyboard("{Escape}");

    await expect
      .poll(() => component.getByRole("option", { name: "atl1-core" }).query())
      .toBeNull();
    await expect.element(component.getByRole("button", { name: "Save" })).toBeVisible();
    await expect.poll(() => component.getByText("Closing form").query()).toBeNull();
    expect(onOpenChange).not.toHaveBeenCalled();
  });

  test("requires at least one member before saving", async () => {
    const component = await render(
      <AddGroupMembersForm
        groupId="group-1"
        membersRelationship={membersRelationship}
        onSuccess={() => {}}
        onCancel={() => {}}
      />
    );

    await component.getByRole("combobox", { name: "Kind" }).click();
    await component.getByRole("option", { name: /Device/ }).click();
    await component.getByRole("button", { name: "Save" }).click();

    await expect.element(component.getByText("Required")).toBeVisible();
    expect(addRelationships).not.toHaveBeenCalled();
  });
});
