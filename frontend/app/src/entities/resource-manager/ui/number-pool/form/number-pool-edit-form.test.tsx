import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { store } from "@/shared/stores";

import { useUpdateObjectMutation } from "@/entities/nodes/object/ui/queries/update-object.mutation";
import { useGetNumberPool } from "@/entities/resource-manager/ui/queries/get-number-pool.query";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../tests/components/render";
import { generateNumberPoolData } from "../../../../../../tests/fake/number-pool";
import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../tests/fake/schema";
import { NumberPoolEditForm } from "./number-pool-edit-form";

vi.mock("@/entities/nodes/object/ui/queries/update-object.mutation", () => ({
  useUpdateObjectMutation: vi.fn(),
}));

vi.mock("@/entities/resource-manager/ui/queries/get-number-pool.query", () => ({
  useGetNumberPool: vi.fn(),
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

describe("NumberPoolEditForm", () => {
  beforeEach(() => {
    store.set(nodeSchemasAtom, [subinterfaceSchema]);
    store.set(genericSchemasAtom, []);
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  test("edits a saved pool, starting from its stored ranges and keeping an empty weight empty", async () => {
    // GIVEN
    vi.mocked(useGetNumberPool).mockReturnValue({
      isPending: false,
      data: generateNumberPoolData({
        id: "pool-id",
        name: { value: "subinterface-units" },
        node: { value: "InfraSubinterface" },
        node_attribute: { value: "unit_id" },
        allocation_scope: { value: ["device"] },
        ranges: [
          { start: 100, end: 199, allocation_weight: 10 },
          { start: 300, end: 399, allocation_weight: null },
        ],
      }),
    } as never);
    const mutateAsync = vi.fn(
      async (
        _params: unknown,
        callbacks?: { onSuccess?: (pool: typeof createdPool) => unknown }
      ) => {
        await callbacks?.onSuccess?.(createdPool);
        return createdPool;
      }
    );
    vi.mocked(useUpdateObjectMutation).mockReturnValue({ mutateAsync } as never);
    const onSuccess = vi.fn();
    const component = await render(<NumberPoolEditForm poolId="pool-id" onSuccess={onSuccess} />);
    await expect.element(component.getByText("Device")).toBeVisible();
    await expect
      .element(component.getByRole("spinbutton", { name: "Weight of range 2" }))
      .toHaveValue(null);

    // WHEN
    await component.getByRole("spinbutton", { name: "End of range 1" }).fill("299");
    await component.getByRole("button", { name: "Save" }).click();

    // THEN
    await expect.poll(() => onSuccess).toHaveBeenCalledWith(createdPool);
    expect(mutateAsync.mock.calls[0]![0]).toEqual({
      objectKind: "CoreNumberPool",
      data: {
        id: "pool-id",
        name: { value: "subinterface-units" },
        description: { value: null },
        ranges: [
          { start: 100, end: 299, allocation_weight: 10 },
          { start: 300, end: 399, allocation_weight: null },
        ],
      },
      processErrorMessage: expect.any(Function),
    });
  });

  test("tells the user why the pool could not be loaded instead of showing an empty form", async () => {
    // GIVEN
    vi.mocked(useGetNumberPool).mockReturnValue({
      isPending: false,
      data: undefined,
      error: new Error("Number pool not found"),
    } as never);
    vi.mocked(useUpdateObjectMutation).mockReturnValue({ mutateAsync: vi.fn() } as never);

    // WHEN
    const component = await render(<NumberPoolEditForm poolId="pool-id" />);

    // THEN
    await expect.element(component.getByText("Number pool not found")).toBeVisible();
    await expect.poll(() => component.getByRole("button", { name: "Save" }).query()).toBeNull();
  });
});
