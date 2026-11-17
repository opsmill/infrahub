import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { queryClient } from "@/shared/api/rest/client";
import { store } from "@/shared/stores";

import type { NodeObject } from "@/entities/nodes/object/domain/model/node";
import { DetailsButtons } from "@/entities/nodes/object/ui/object-details/action-buttons/details-buttons";
import ObjectEdit from "@/entities/nodes/object/ui/object-edit/object-item-edit-paginated";
import { ObjectActionsCell } from "@/entities/nodes/object/ui/object-table/cells/object-actions-cell";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import { RelationshipActionsCell } from "@/entities/nodes/relationships/ui/relationship-table/relationship-actions-cell";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../tests/components/render";
import { generatePermission } from "../../../../../../tests/fake/permission";
import { generateNodeSchema } from "../../../../../../tests/fake/schema";
import { ObjectEditSheet } from "./object-edit-sheet";

vi.mock("@/entities/nodes/object/ui/object-edit/object-item-edit-paginated", () => ({
  default: vi.fn(
    ({
      closeDrawer,
      onUpdateComplete,
    }: {
      closeDrawer: () => void;
      onUpdateComplete?: () => void;
    }) => (
      <div>
        <button type="button" onClick={closeDrawer}>
          Cancel
        </button>
        <button type="button" onClick={() => onUpdateComplete?.()}>
          Save
        </button>
      </div>
    )
  ),
}));

const objectEditMock = vi.mocked(ObjectEdit);

const deviceSchema = generateNodeSchema({
  kind: "TestDevice",
  namespace: "Test",
  name: "Device",
  label: "Device",
  description: "Network device in a rack",
});

const interfaceSchema = generateNodeSchema({
  kind: "TestInterface",
  namespace: "Test",
  name: "Interface",
  label: "Interface",
  description: "Physical port on a device",
});

const device = {
  id: "device-1",
  __typename: "TestDevice",
  display_label: "atl1-edge",
} as NodeObject;

const initialNodeSchemas = store.get(nodeSchemasAtom);

beforeAll(() => {
  store.set(nodeSchemasAtom, [deviceSchema, interfaceSchema]);
});

afterAll(() => {
  store.set(nodeSchemasAtom, initialNodeSchemas);
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.clearAllMocks();
});

describe("ObjectEditSheet", () => {
  it("shows the edit title, the schema and node breadcrumb, and the subtitle", async () => {
    // GIVEN
    const subtitle = "Edit the device and its peers";

    // WHEN
    const component = await render(
      <ObjectEditSheet
        isOpen
        onOpenChange={vi.fn()}
        schema={deviceSchema}
        objectId="device-1"
        objectLabel="atl1-edge"
        subtitle={subtitle}
      />
    );

    // THEN
    await expect
      .element(component.getByRole("heading", { name: "Edit atl1-edge", exact: true }))
      .toBeVisible();
    await expect.element(component.getByText(/^Device\s*atl1-edge$/)).toBeVisible();
    await expect.element(component.getByText(subtitle, { exact: true })).toBeVisible();
  });

  it("does not show the schema description when no subtitle is given", async () => {
    // GIVEN
    const props = { schema: deviceSchema, objectId: "device-1", objectLabel: "atl1-edge" };

    // WHEN
    const component = await render(<ObjectEditSheet isOpen onOpenChange={vi.fn()} {...props} />);

    // THEN
    await expect
      .element(component.getByRole("heading", { name: "Edit atl1-edge", exact: true }))
      .toBeVisible();
    await expect.element(component.getByText("Network device in a rack")).not.toBeInTheDocument();
  });

  it("does not mount the edit form while closed", async () => {
    // GIVEN
    const props = { schema: deviceSchema, objectId: "device-1", objectLabel: "atl1-edge" };

    // WHEN
    const component = await render(
      <ObjectEditSheet isOpen={false} onOpenChange={vi.fn()} {...props} />
    );

    // THEN
    await expect.element(component.getByRole("dialog")).not.toBeInTheDocument();
    expect(objectEditMock).not.toHaveBeenCalled();
  });

  it("closes without refreshing objects when the form is cancelled", async () => {
    // GIVEN
    const onOpenChange = vi.fn();
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");
    const component = await render(
      <ObjectEditSheet
        isOpen
        onOpenChange={onOpenChange}
        schema={deviceSchema}
        objectId="device-1"
        objectLabel="atl1-edge"
      />
    );

    // WHEN
    await component.getByRole("button", { name: "Cancel", exact: true }).click();

    // THEN
    expect(onOpenChange).toHaveBeenCalledExactlyOnceWith(false);
    expect(invalidateQueries).not.toHaveBeenCalled();
  });

  it("stays open until the object queries are refreshed after an update", async () => {
    // GIVEN
    const onOpenChange = vi.fn();
    const invalidateQueries = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockReturnValue(new Promise(() => {}));
    const component = await render(
      <ObjectEditSheet
        isOpen
        onOpenChange={onOpenChange}
        schema={deviceSchema}
        objectId="device-1"
        objectLabel="atl1-edge"
      />
    );

    // WHEN
    await component.getByRole("button", { name: "Save", exact: true }).click();

    // THEN
    expect(invalidateQueries).toHaveBeenCalledExactlyOnceWith({ queryKey: objectQueryKeys.all });
    expect(onOpenChange).not.toHaveBeenCalled();
  });

  it("closes after the object queries are refreshed when the update completes", async () => {
    // GIVEN
    const calls: object[] = [];
    const onOpenChange = vi.fn((isOpen: boolean) => calls.push({ isOpen }));
    vi.spyOn(queryClient, "invalidateQueries").mockImplementation(async (filters) => {
      calls.push({ invalidated: filters });
    });
    const component = await render(
      <ObjectEditSheet
        isOpen
        onOpenChange={onOpenChange}
        schema={deviceSchema}
        objectId="device-1"
        objectLabel="atl1-edge"
      />
    );

    // WHEN
    await component.getByRole("button", { name: "Save", exact: true }).click();

    // THEN
    await vi.waitFor(() =>
      expect(calls).toEqual([{ invalidated: { queryKey: objectQueryKeys.all } }, { isOpen: false }])
    );
  });

  it.each([
    {
      name: "the schema kind by default",
      props: {},
      expected: { objectKind: "TestDevice", extraRelationshipNames: undefined },
    },
    {
      name: "the given kind and extra relationships",
      props: { objectKind: "TestInterface", extraRelationshipNames: ["connected_endpoint"] },
      expected: { objectKind: "TestInterface", extraRelationshipNames: ["connected_endpoint"] },
    },
  ])("edits $name", async ({ props, expected }) => {
    // GIVEN
    const onOpenChange = vi.fn();

    // WHEN
    await render(
      <ObjectEditSheet
        isOpen
        onOpenChange={onOpenChange}
        schema={deviceSchema}
        objectId="node-1"
        objectLabel="atl1-edge"
        {...props}
      />
    );

    // THEN
    expect(objectEditMock.mock.lastCall?.[0]).toMatchObject({ objectId: "node-1", ...expected });
  });
});

describe("ObjectEditSheet callers", () => {
  it("opens from the details Edit button with the schema description as subtitle", async () => {
    // GIVEN
    const component = await render(
      <DetailsButtons
        schema={deviceSchema}
        objectDetailsData={device}
        permission={generatePermission()}
      />
    );

    // WHEN
    await component.getByRole("button", { name: "Edit", exact: true }).click();

    // THEN
    await expect
      .element(component.getByRole("heading", { name: "Edit atl1-edge", exact: true }))
      .toBeVisible();
    await expect
      .element(component.getByText("Network device in a rack", { exact: true }))
      .toBeVisible();
    expect(objectEditMock.mock.lastCall?.[0]).toMatchObject({
      objectId: "device-1",
      objectKind: "TestDevice",
    });
  });

  it("closes the details edit sheet after the object queries are refreshed", async () => {
    // GIVEN
    const invalidateQueries = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockResolvedValue(undefined);
    const component = await render(
      <DetailsButtons
        schema={deviceSchema}
        objectDetailsData={device}
        permission={generatePermission()}
      />
    );
    await component.getByRole("button", { name: "Edit", exact: true }).click();

    // WHEN
    await component.getByRole("button", { name: "Save", exact: true }).click();

    // THEN
    await expect.element(component.getByRole("dialog")).not.toBeInTheDocument();
    expect(invalidateQueries).toHaveBeenCalledExactlyOnceWith({ queryKey: objectQueryKeys.all });
  });

  it("opens from the object table actions with its extra relationships and no subtitle", async () => {
    // GIVEN
    const component = await render(
      <ObjectActionsCell
        objectKind="TestDevice"
        objectId="device-1"
        objectLabel="atl1-edge"
        permission={generatePermission()}
        extraRelationshipNames={["interfaces"]}
      />
    );
    await component.getByTestId("actions-cell-atl1-edge").click();

    // WHEN
    await component.getByRole("menuitem", { name: "Edit", exact: true }).click();

    // THEN
    await expect
      .element(component.getByRole("heading", { name: "Edit atl1-edge", exact: true }))
      .toBeVisible();
    await expect.element(component.getByText("Network device in a rack")).not.toBeInTheDocument();
    expect(objectEditMock.mock.lastCall?.[0]).toMatchObject({
      objectId: "device-1",
      objectKind: "TestDevice",
      extraRelationshipNames: ["interfaces"],
    });
  });

  it("opens from the relationship table actions with the parent schema and the peer kind", async () => {
    // GIVEN
    const component = await render(
      <RelationshipActionsCell
        parentId="device-1"
        parentKind="TestDevice"
        permission={generatePermission()}
        relationshipId="interface-1"
        relationshipKind="TestInterface"
        relationshipLabel="eth0"
        relationshipName="interfaces"
        relationshipsCount={1}
      />
    );
    await component.getByTestId("actions-cell-eth0").click();

    // WHEN
    await component.getByRole("menuitem", { name: "Edit", exact: true }).click();

    // THEN
    await expect
      .element(component.getByRole("heading", { name: "Edit eth0", exact: true }))
      .toBeVisible();
    await expect.element(component.getByText(/^Device\s*eth0$/)).toBeVisible();
    expect(objectEditMock.mock.lastCall?.[0]).toMatchObject({
      objectId: "interface-1",
      objectKind: "TestInterface",
    });
  });
});
