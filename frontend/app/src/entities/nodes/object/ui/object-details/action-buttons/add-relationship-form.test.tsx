import { beforeEach, describe, expect, test, vi } from "vitest";

import { store } from "@/shared/stores";

import type { NodeObject } from "@/entities/nodes/object/domain/model/node";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../../tests/components/render";
import {
  generateGenericSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../../tests/fake/schema";
import { AddRelationshipForm } from "./add-relationship-form";

vi.mock("@/shared/components/form/object-form", () => ({
  default: () => <div>Create peer form</div>,
}));
vi.mock("@/entities/groups/ui/add-group-members-form", () => ({
  AddGroupMembersForm: () => <div>Add group members form</div>,
}));
vi.mock("@/entities/nodes/object/ui/object-details/action-buttons/select-peer-form", async () => {
  const { useCurrentFormContext } = await import("@/shared/components/form/utils/form-context");
  return {
    SelectPeerForm: () => {
      const { parentData } = useCurrentFormContext();
      return (
        <div>
          <p>Select peer form</p>
          <p>Form context object: {parentData?.display_label}</p>
        </div>
      );
    },
  };
});

describe("AddRelationshipForm", () => {
  const genericDevice = generateGenericSchema({
    kind: "TestGenericDevice",
    name: "GenericDevice",
    label: "Generic Device",
    relationships: [],
    used_by: ["TestDevice"],
  });

  const buildInterfaceSchema = (deviceRelationshipPeer: string) =>
    generateNodeSchema({
      kind: "TestInterface",
      name: "Interface",
      label: "Interface",
      relationships: [
        generateRelationshipSchema({
          name: "device",
          peer: deviceRelationshipPeer,
          kind: "Parent",
          cardinality: "one",
          optional: false,
        }),
      ],
    });

  const interfacesRelationship = generateRelationshipSchema({
    name: "interfaces",
    peer: "TestInterface",
    kind: "Component",
    cardinality: "many",
  });

  const deviceSchema = generateNodeSchema({
    kind: "TestDevice",
    name: "Device",
    label: "Device",
    inherit_from: ["TestGenericDevice"],
    relationships: [interfacesRelationship],
  });

  const deviceData = {
    id: "device-1",
    __typename: "TestDevice",
    display_label: "atl1-edge",
  } as unknown as NodeObject;

  const membersRelationship = generateRelationshipSchema({
    name: "members",
    peer: "CoreNode",
    kind: "Generic",
    cardinality: "many",
  });

  const onSuccess = vi.fn(async () => {});
  const onCancel = vi.fn();

  beforeEach(() => {
    store.set(genericSchemasAtom, [genericDevice]);
  });

  test("creates a new peer when the peer's required Parent relationship points to a generic the object inherits from", async () => {
    // GIVEN
    store.set(nodeSchemasAtom, [deviceSchema, buildInterfaceSchema("TestGenericDevice")]);

    // WHEN
    const component = await render(
      <AddRelationshipForm
        objectData={deviceData}
        objectSchema={deviceSchema}
        relationshipSchema={interfacesRelationship}
        onSuccess={onSuccess}
        onCancel={onCancel}
      />
    );

    // THEN
    await expect.element(component.getByText("Create peer form")).toBeVisible();
    await expect.poll(() => component.getByText("Select peer form").query()).toBeNull();
  });

  test("selects an existing peer when the peer has no required Parent relationship back to the object", async () => {
    // GIVEN
    store.set(nodeSchemasAtom, [deviceSchema, buildInterfaceSchema("TestUnrelatedDevice")]);

    // WHEN
    const component = await render(
      <AddRelationshipForm
        objectData={deviceData}
        objectSchema={deviceSchema}
        relationshipSchema={interfacesRelationship}
        onSuccess={onSuccess}
        onCancel={onCancel}
      />
    );

    // THEN
    await expect.element(component.getByText("Select peer form")).toBeVisible();
    await expect.poll(() => component.getByText("Create peer form").query()).toBeNull();
  });

  test("adds several members at once on a group's members relationship", async () => {
    // GIVEN
    const groupSchema = generateNodeSchema({
      kind: "TestStandardGroup",
      name: "StandardGroup",
      label: "Standard Group",
      inherit_from: ["CoreGroup"],
      relationships: [membersRelationship],
    });
    store.set(nodeSchemasAtom, [groupSchema]);

    // WHEN
    const component = await render(
      <AddRelationshipForm
        objectData={{ id: "group-1", __typename: "TestStandardGroup" } as unknown as NodeObject}
        objectSchema={groupSchema}
        relationshipSchema={membersRelationship}
        onSuccess={onSuccess}
        onCancel={onCancel}
      />
    );

    // THEN
    await expect.element(component.getByText("Add group members form")).toBeVisible();
    await expect.poll(() => component.getByText("Select peer form").query()).toBeNull();
  });

  test("selects one peer on a members relationship of a node that is not a group", async () => {
    // GIVEN
    const teamSchema = generateNodeSchema({
      kind: "TestTeam",
      name: "Team",
      label: "Team",
      inherit_from: [],
      relationships: [membersRelationship],
    });
    store.set(nodeSchemasAtom, [teamSchema]);

    // WHEN
    const component = await render(
      <AddRelationshipForm
        objectData={{ id: "team-1", __typename: "TestTeam" } as unknown as NodeObject}
        objectSchema={teamSchema}
        relationshipSchema={membersRelationship}
        onSuccess={onSuccess}
        onCancel={onCancel}
      />
    );

    // THEN
    await expect.element(component.getByText("Select peer form")).toBeVisible();
    await expect.poll(() => component.getByText("Add group members form").query()).toBeNull();
  });

  test("gives the chosen form the object as form context", async () => {
    // GIVEN
    store.set(nodeSchemasAtom, [deviceSchema, buildInterfaceSchema("TestUnrelatedDevice")]);

    // WHEN
    const component = await render(
      <AddRelationshipForm
        objectData={deviceData}
        objectSchema={deviceSchema}
        relationshipSchema={interfacesRelationship}
        onSuccess={onSuccess}
        onCancel={onCancel}
      />
    );

    // THEN
    await expect.element(component.getByText("Form context object: atl1-edge")).toBeVisible();
  });
});
