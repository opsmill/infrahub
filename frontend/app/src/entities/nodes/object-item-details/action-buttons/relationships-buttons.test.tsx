import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { store } from "@/shared/stores";

import type { NodeObject } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../tests/components/render";
import {
  generateGenericSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../tests/fake/schema";
import { RelationshipsButtons } from "./relationships-buttons";

vi.mock("@/shared/components/form/object-form", () => ({
  default: () => <div data-testid="object-create-form">create form</div>,
}));
vi.mock("@/shared/components/form/dynamic-form", () => ({
  default: () => <div data-testid="associate-form">associate form</div>,
}));

describe("RelationshipsButtons", () => {
  const genericDevice = generateGenericSchema({
    kind: "TestGenericDevice",
    name: "GenericDevice",
    label: "Generic Device",
    relationships: [],
    used_by: ["TestDevice"],
  });

  // The parent relationship on the child peers the GENERIC, not the concrete node.
  const buildInterfaceSchema = (deviceRelPeer: string) =>
    generateNodeSchema({
      kind: "TestInterface",
      name: "Interface",
      label: "Interface",
      relationships: [
        generateRelationshipSchema({
          name: "device",
          peer: deviceRelPeer,
          kind: "Parent",
          cardinality: "one",
          optional: false,
        }),
      ],
    });

  const deviceSchema = generateNodeSchema({
    kind: "TestDevice",
    name: "Device",
    label: "Device",
    inherit_from: ["TestGenericDevice"],
    relationships: [
      generateRelationshipSchema({
        name: "interfaces",
        peer: "TestInterface",
        kind: "Component",
        cardinality: "many",
      }),
    ],
  });

  const objectDetailsData = {
    id: "device-1",
    __typename: "TestDevice",
    display_label: "atl1-edge",
  } as unknown as NodeObject;

  const permission = {
    create: { isAllowed: true, message: null },
  } as unknown as Permission;

  beforeEach(() => {
    store.set(genericSchemasAtom, [genericDevice]);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("opens the create form directly when the child's Parent relationship peers a generic the object inherits from", async () => {
    // GIVEN the child's `device` Parent relationship peers the generic TestGenericDevice,
    // which the viewed concrete node TestDevice inherits from.
    store.set(nodeSchemasAtom, [deviceSchema, buildInterfaceSchema("TestGenericDevice")]);

    const component = await render(
      <RelationshipsButtons
        permission={permission}
        schema={deviceSchema}
        objectDetailsData={objectDetailsData}
        relationshipName="interfaces"
      />
    );

    // WHEN opening the add drawer
    await component.getByTestId("open-relationship-form-button").click();

    // THEN the direct create form is shown, not the associate/relate form.
    await expect.element(component.getByTestId("object-create-form")).toBeVisible();
    await expect.poll(() => component.getByTestId("associate-form").query()).toBeNull();
  });

  test("shows the associate form when the peer has no Parent relationship back to the object", async () => {
    // GIVEN the child's `device` Parent relationship peers an unrelated kind
    // that the viewed object neither is nor inherits from.
    store.set(nodeSchemasAtom, [deviceSchema, buildInterfaceSchema("TestUnrelatedDevice")]);

    const component = await render(
      <RelationshipsButtons
        permission={permission}
        schema={deviceSchema}
        objectDetailsData={objectDetailsData}
        relationshipName="interfaces"
      />
    );

    // WHEN opening the add drawer
    await component.getByTestId("open-relationship-form-button").click();

    // THEN the associate/relate form is shown.
    await expect.element(component.getByTestId("associate-form")).toBeVisible();
    await expect.poll(() => component.getByTestId("object-create-form").query()).toBeNull();
  });
});
