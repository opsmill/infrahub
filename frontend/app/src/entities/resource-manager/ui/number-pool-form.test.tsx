import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, test, vi } from "vitest";

import { store } from "@/shared/stores";

import { useCreateObjectMutation } from "@/entities/nodes/object/ui/queries/create-object.mutation";
import { useUpdateObjectMutation } from "@/entities/nodes/object/ui/queries/update-object.mutation";
import type { NumberPoolForEditing } from "@/entities/resource-manager/domain/model/number-pool-range";
import { getNumberPoolForEditing } from "@/entities/resource-manager/domain/use-cases/get-number-pool-for-editing";
import { NumberPoolForm } from "@/entities/resource-manager/ui/number-pool-form";
import { useApplyNumberPoolRangeChangesMutation } from "@/entities/resource-manager/ui/queries/apply-number-pool-range-changes.mutation";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../tests/components/render";
import { generateAttributeSchema, generateNodeSchema } from "../../../../tests/fake/schema";

vi.mock("@/entities/nodes/object/ui/queries/create-object.mutation");
vi.mock("@/entities/nodes/object/ui/queries/update-object.mutation");
vi.mock("@/entities/resource-manager/ui/queries/apply-number-pool-range-changes.mutation");
vi.mock("@/entities/resource-manager/domain/use-cases/get-number-pool-for-editing");

const interfaceSchema = generateNodeSchema({
  id: "interface",
  kind: "InfraInterface",
  name: "Interface",
  namespace: "Infra",
  label: "Interface",
  attributes: [generateAttributeSchema({ name: "speed", label: "Speed", kind: "Number" })],
});

const createdPool = { id: "pool-1", display_label: "VLAN pool", __typename: "CoreNumberPool" };

const storedPool: NumberPoolForEditing = {
  id: "pool-1",
  name: "VLAN pool",
  description: "",
  node: "InfraInterface",
  nodeAttribute: "speed",
  allocationScope: [],
  poolType: "User",
  ranges: [{ id: "range-1", start: 100, end: 199, weight: 10 }],
};

const RANGE_REFUSED = "Range 300-399 overlaps another range";

describe("NumberPoolForm", () => {
  const initialNodeSchemas = store.get(nodeSchemasAtom);
  const initialGenericSchemas = store.get(genericSchemasAtom);
  const createPool = vi.fn();
  const applyRangeChanges = vi.fn();
  const onSuccess = vi.fn();

  beforeAll(() => {
    store.set(nodeSchemasAtom, [interfaceSchema]);
    store.set(genericSchemasAtom, []);
  });

  afterAll(() => {
    store.set(nodeSchemasAtom, initialNodeSchemas);
    store.set(genericSchemasAtom, initialGenericSchemas);
  });

  beforeEach(() => {
    createPool.mockResolvedValue(createdPool);
    applyRangeChanges.mockResolvedValue({ appliedCount: 2, errorMessage: null });
    vi.mocked(getNumberPoolForEditing).mockResolvedValue(storedPool);
    vi.mocked(useCreateObjectMutation).mockReturnValue({
      mutateAsync: createPool,
    } as unknown as ReturnType<typeof useCreateObjectMutation>);
    vi.mocked(useUpdateObjectMutation).mockReturnValue({
      mutateAsync: vi.fn(),
    } as unknown as ReturnType<typeof useUpdateObjectMutation>);
    vi.mocked(useApplyNumberPoolRangeChangesMutation).mockReturnValue({
      mutateAsync: applyRangeChanges,
    } as unknown as ReturnType<typeof useApplyNumberPoolRangeChangesMutation>);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  async function renderFilledCreateForm() {
    const component = await render(<NumberPoolForm onSuccess={onSuccess} />);
    await component.getByLabelText("Name *").fill("VLAN pool");
    await component.getByRole("combobox", { name: "Node *" }).click();
    await component.getByRole("option", { name: "Interface Infra" }).click();
    await component.getByRole("combobox", { name: "Attribute *" }).click();
    await component.getByRole("option", { name: "Speed" }).click();
    await component.getByRole("textbox", { name: "Start" }).fill("100");
    await component.getByRole("textbox", { name: "End" }).fill("199");
    await component.getByRole("textbox", { name: "Weight" }).fill("10");
    await component.getByRole("button", { name: "Add range" }).click();
    await component.getByRole("textbox", { name: "Start" }).nth(1).fill("300");
    await component.getByRole("textbox", { name: "End" }).nth(1).fill("399");
    return component;
  }

  test("shows one empty range row instead of the single start and end range fields", async () => {
    // GIVEN
    const props = { onSuccess };

    // WHEN
    const component = await render(<NumberPoolForm {...props} />);

    // THEN
    await expect.element(component.getByRole("textbox", { name: "Start" })).toHaveValue("");
    await expect.element(component.getByText("Start range")).not.toBeInTheDocument();
    await expect.element(component.getByText("End range")).not.toBeInTheDocument();
  });

  test("creates the pool without its ranges, then creates each range and closes", async () => {
    // GIVEN
    const component = await renderFilledCreateForm();

    // WHEN
    await component.getByRole("button", { name: "Save" }).click();

    // THEN
    await expect.poll(() => onSuccess).toHaveBeenCalledWith(createdPool);
    expect(createPool).toHaveBeenCalledWith({
      objectKind: "CoreNumberPool",
      data: {
        name: { value: "VLAN pool" },
        node: { value: "InfraInterface" },
        node_attribute: { value: "speed" },
      },
    });
    expect(applyRangeChanges).toHaveBeenCalledWith({
      poolId: "pool-1",
      changes: {
        deletes: [],
        smaller: [],
        larger: [],
        creates: [
          { start: 100, end: 199, weight: 10 },
          { start: 300, end: 399, weight: null },
        ],
      },
    });
  });

  test("keeps the form open with the rows as typed and shows the range refusal once", async () => {
    // GIVEN
    applyRangeChanges.mockResolvedValue({ appliedCount: 1, errorMessage: RANGE_REFUSED });
    const component = await renderFilledCreateForm();

    // WHEN
    await component.getByRole("button", { name: "Save" }).click();

    // THEN
    await expect.element(component.getByText(RANGE_REFUSED)).toBeVisible();
    expect(component.getByText(RANGE_REFUSED).elements()).toHaveLength(1);
    await expect
      .element(component.getByRole("textbox", { name: "Start" }).nth(1))
      .toHaveValue("300");
    expect(onSuccess).not.toHaveBeenCalled();
  });

  test("shows the node and attribute of the created pool as read-only after a range refusal", async () => {
    // GIVEN
    applyRangeChanges.mockResolvedValue({ appliedCount: 1, errorMessage: RANGE_REFUSED });
    const component = await renderFilledCreateForm();

    // WHEN
    await component.getByRole("button", { name: "Save" }).click();

    // THEN
    await expect.element(component.getByText("Not scoped")).toBeVisible();
    expect(component.getByRole("combobox", { name: "Node *" }).elements()).toHaveLength(0);
  });

  test("saving again after a range refusal does not create a second pool and sends only the remaining ranges", async () => {
    // GIVEN
    applyRangeChanges.mockResolvedValueOnce({ appliedCount: 1, errorMessage: RANGE_REFUSED });
    const component = await renderFilledCreateForm();
    await component.getByRole("button", { name: "Save" }).click();
    await expect.element(component.getByText(RANGE_REFUSED)).toBeVisible();

    // WHEN
    await component.getByRole("button", { name: "Save" }).click();

    // THEN
    await expect.poll(() => onSuccess).toHaveBeenCalledWith(createdPool);
    expect(createPool).toHaveBeenCalledTimes(1);
    expect(applyRangeChanges).toHaveBeenLastCalledWith({
      poolId: "pool-1",
      changes: {
        deletes: [],
        smaller: [],
        larger: [],
        creates: [{ start: 300, end: 399, weight: null }],
      },
    });
  });
});
