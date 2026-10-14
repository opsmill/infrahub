import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { userEvent } from "vitest/browser";

import { store } from "@/shared/stores";

import { useCreateObjectMutation } from "@/entities/nodes/object/ui/queries/create-object.mutation";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../tests/components/render";
import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../tests/fake/schema";
import { NumberPoolCreateForm } from "./number-pool-create-form";

vi.mock("@/entities/nodes/object/ui/queries/create-object.mutation", () => ({
  useCreateObjectMutation: vi.fn(),
}));

const subinterfaceSchema = generateNodeSchema({
  kind: "InfraSubinterface",
  label: "Subinterface",
  attributes: [generateAttributeSchema({ name: "unit_id", label: "Unit ID", kind: "Number" })],
  relationships: [
    generateRelationshipSchema({
      name: "device",
      label: "Device",
      cardinality: "one",
      optional: false,
    }),
  ],
});

const createdPool = {
  id: "pool-id",
  display_label: "subinterface-units",
  __typename: "CoreNumberPool",
};

interface CreateParams {
  processErrorMessage?: (message: string) => void;
}

function mockCreate(outcome: { pool: typeof createdPool } | { error: string }) {
  const mutateAsync = vi.fn(
    async (
      params: CreateParams,
      callbacks?: { onSuccess?: (pool: typeof createdPool) => unknown }
    ) => {
      if ("error" in outcome) {
        // Stops before the client's rejection, which the form leaves unhandled.
        params.processErrorMessage?.(outcome.error);
        return;
      }
      await callbacks?.onSuccess?.(outcome.pool);
      return outcome.pool;
    }
  );
  vi.mocked(useCreateObjectMutation).mockReturnValue({ mutateAsync } as never);
  return mutateAsync;
}

async function fillValidPool(component: Awaited<ReturnType<typeof render>>) {
  await component.getByRole("textbox", { name: "Name *" }).fill("subinterface-units");
  await component.getByRole("button", { name: "Node" }).click();
  await component.getByRole("option", { name: /Subinterface/ }).click();
  await component.getByRole("button", { name: /Attribute$/ }).click();
  await component.getByRole("option", { name: /Unit ID/ }).click();
  await component.getByRole("button", { name: "Add a relationship or attribute" }).click();
  await component.getByRole("option", { name: "Device" }).click();
  await userEvent.keyboard("{Escape}");
  await component.getByRole("spinbutton", { name: "Start of range 1" }).fill("100");
  await component.getByRole("spinbutton", { name: "End of range 1" }).fill("199");
  await component.getByRole("spinbutton", { name: "Weight of range 1" }).fill("10");
}

describe("NumberPoolCreateForm", () => {
  beforeEach(() => {
    store.set(nodeSchemasAtom, [subinterfaceSchema]);
    store.set(genericSchemasAtom, []);
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  test("creates the pool with its scope and ranges in one save, then hands the pool to the caller", async () => {
    // GIVEN
    const mutateAsync = mockCreate({ pool: createdPool });
    const onSuccess = vi.fn();
    const component = await render(<NumberPoolCreateForm onSuccess={onSuccess} />);
    await fillValidPool(component);

    // WHEN
    await component.getByRole("button", { name: "Save" }).click();

    // THEN
    await expect.poll(() => onSuccess).toHaveBeenCalledWith(createdPool);
    expect(mutateAsync).toHaveBeenCalledTimes(1);
    expect(mutateAsync.mock.calls[0]![0]).toMatchObject({
      objectKind: "CoreNumberPool",
      data: {
        name: { value: "subinterface-units" },
        node: { value: "InfraSubinterface" },
        node_attribute: { value: "unit_id" },
        allocation_scope: { value: ["device"] },
        ranges: [{ start: 100, end: 199, allocation_weight: 10 }],
      },
      processErrorMessage: expect.any(Function),
    });
  });

  test("sends nothing while two ranges overlap", async () => {
    // GIVEN
    const mutateAsync = mockCreate({ pool: createdPool });
    const component = await render(<NumberPoolCreateForm />);
    await fillValidPool(component);
    await component.getByRole("button", { name: "Add range" }).click();
    await component.getByRole("spinbutton", { name: "Start of range 2" }).fill("150");
    await component.getByRole("spinbutton", { name: "End of range 2" }).fill("250");

    // WHEN
    await component.getByRole("button", { name: "Save" }).click();

    // THEN
    await expect.element(component.getByText("Overlaps 150 – 250")).toBeVisible();
    await expect.element(component.getByText("Overlaps 100 – 199")).toBeVisible();
    expect(mutateAsync).not.toHaveBeenCalled();
  });

  test("keeps the values and shows the backend's refusal above the footer", async () => {
    // GIVEN
    mockCreate({ error: "Range 100-199 ends above the attribute's max_value (150)" });
    const component = await render(<NumberPoolCreateForm />);
    await fillValidPool(component);

    // WHEN
    await component.getByRole("button", { name: "Save" }).click();

    // THEN
    await expect
      .element(component.getByRole("alert"))
      .toHaveTextContent("Range 100-199 ends above the attribute's max_value (150)");
    await expect
      .element(component.getByRole("spinbutton", { name: "End of range 1" }))
      .toHaveValue(199);
  });
});
