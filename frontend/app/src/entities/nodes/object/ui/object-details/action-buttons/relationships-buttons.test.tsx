import { beforeEach, describe, expect, test, vi } from "vitest";

import { store } from "@/shared/stores";

import type { NodeObject } from "@/entities/nodes/object/domain/model/node";
import type { Permission } from "@/entities/permission/domain/model/permission";
import { genericSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../../tests/components/render";
import {
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../../tests/fake/schema";
import { RelationshipsButtons } from "./relationships-buttons";

vi.mock("@/entities/nodes/object/ui/object-details/action-buttons/add-relationship-form", () => ({
  AddRelationshipForm: ({ relationshipSchema }: { relationshipSchema: { name: string } }) => (
    <div>Add relationship form for {relationshipSchema.name}</div>
  ),
}));

describe("RelationshipsButtons", () => {
  const deviceSchema = generateNodeSchema({
    kind: "TestDevice",
    name: "Device",
    label: "Device",
    relationships: [
      generateRelationshipSchema({
        name: "interfaces",
        label: "Interfaces",
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
    store.set(genericSchemasAtom, []);
  });

  test("opens the add form of the selected relationship in a drawer", async () => {
    // GIVEN
    const component = await render(
      <RelationshipsButtons
        permission={permission}
        schema={deviceSchema}
        objectDetailsData={objectDetailsData}
        relationshipName="interfaces"
      />
    );

    // WHEN
    await component.getByRole("button", { name: "Add Interfaces" }).click();

    // THEN
    await expect.element(component.getByText("Add relationship form for interfaces")).toBeVisible();
  });
});
