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
  relationships: [
    {
      ...generateNodeSchema().relationships![0]!,
      name: "device",
      label: "Device",
      peer: "InfraDevice",
      kind: "Parent",
      cardinality: "one",
      optional: false,
    },
  ],
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
  const updatePool = vi.fn();
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
    updatePool.mockResolvedValue(createdPool);
    applyRangeChanges.mockResolvedValue({ errorMessage: null });
    vi.mocked(getNumberPoolForEditing).mockResolvedValue(storedPool);
    vi.mocked(useCreateObjectMutation).mockReturnValue({
      mutateAsync: createPool,
    } as unknown as ReturnType<typeof useCreateObjectMutation>);
    vi.mocked(useUpdateObjectMutation).mockReturnValue({
      mutateAsync: updatePool,
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

  test("creates the pool with the chosen scope as bare field names", async () => {
    // GIVEN
    const component = await renderFilledCreateForm();
    await component.getByRole("button", { name: "No relationship or attribute" }).click();
    await component.getByRole("option", { name: /^Device/ }).click();

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
        allocation_scope: { value: ["device"] },
      },
    });
  });

  test("keeps the form open with the rows as typed and shows the range refusal once", async () => {
    // GIVEN
    applyRangeChanges.mockResolvedValue({ errorMessage: RANGE_REFUSED });
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
    applyRangeChanges.mockResolvedValue({ errorMessage: RANGE_REFUSED });
    const component = await renderFilledCreateForm();

    // WHEN
    await component.getByRole("button", { name: "Save" }).click();

    // THEN
    await expect.element(component.getByText("Not scoped")).toBeVisible();
    expect(component.getByRole("combobox", { name: "Node *" }).elements()).toHaveLength(0);
  });

  test("saving again after a range refusal does not create a second pool and sends only the remaining ranges", async () => {
    // GIVEN
    applyRangeChanges.mockResolvedValueOnce({ errorMessage: RANGE_REFUSED });
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

  describe("edit", () => {
    const poolWithRanges: NumberPoolForEditing = {
      ...storedPool,
      ranges: [
        { id: "range-3", start: 600, end: 699, weight: null },
        { id: "range-2", start: 300, end: 399, weight: null },
        { id: "range-1", start: 100, end: 199, weight: 10 },
      ],
    };
    const currentObject = { id: "pool-1" } as NonNullable<
      Parameters<typeof NumberPoolForm>[0]["currentObject"]
    >;

    async function renderEditForm() {
      vi.mocked(getNumberPoolForEditing).mockResolvedValue(poolWithRanges);
      const component = await render(
        <NumberPoolForm currentObject={currentObject} onSuccess={onSuccess} />
      );
      await expect.element(component.getByRole("textbox", { name: "Start" }).first()).toBeVisible();
      return component;
    }

    test("lists the stored ranges by weight then start, with node and attribute as read-only text", async () => {
      // GIVEN
      vi.mocked(getNumberPoolForEditing).mockResolvedValue(poolWithRanges);

      // WHEN
      const component = await render(<NumberPoolForm currentObject={currentObject} />);

      // THEN
      await expect.element(component.getByText("Not scoped")).toBeVisible();
      const starts = component.getByRole("textbox", { name: "Start" });
      await expect.element(starts.nth(0)).toHaveValue("100");
      await expect.element(starts.nth(1)).toHaveValue("300");
      await expect.element(starts.nth(2)).toHaveValue("600");
      expect(component.getByRole("combobox", { name: "Node *" }).elements()).toHaveLength(0);
    });

    test("a name-only change updates the pool and sends no range call", async () => {
      // GIVEN
      const component = await renderEditForm();
      await component.getByLabelText("Name *").fill("Renamed pool");

      // WHEN
      await component.getByRole("button", { name: "Save" }).click();

      // THEN
      await expect.poll(() => onSuccess).toHaveBeenCalled();
      expect(updatePool).toHaveBeenCalledWith({
        objectKind: "CoreNumberPool",
        data: { id: "pool-1", name: { value: "Renamed pool" } },
      });
      expect(applyRangeChanges).not.toHaveBeenCalled();
    });

    test("sends only the changed ranges, grouped as removals, smaller, larger and additions", async () => {
      // GIVEN
      const component = await renderEditForm();
      const ends = component.getByRole("textbox", { name: "End" });
      await ends.nth(0).fill("150");
      await ends.nth(1).fill("450");
      await component.getByRole("button", { name: "Remove range" }).nth(2).click();
      await component.getByRole("button", { name: "Add range" }).click();
      await component.getByRole("textbox", { name: "Start" }).nth(2).fill("800");
      await component.getByRole("textbox", { name: "End" }).nth(2).fill("899");

      // WHEN
      await component.getByRole("button", { name: "Save" }).click();

      // THEN
      await expect.poll(() => onSuccess).toHaveBeenCalled();
      expect(updatePool).not.toHaveBeenCalled();
      expect(applyRangeChanges).toHaveBeenCalledWith({
        poolId: "pool-1",
        changes: {
          deletes: ["range-3"],
          smaller: [{ id: "range-1", start: 100, end: 150, weight: 10 }],
          larger: [{ id: "range-2", start: 300, end: 450, weight: null }],
          creates: [{ start: 800, end: 899, weight: null }],
        },
      });
    });

    test("after a refusal mid-sequence, keeps the rows as typed and the next save sends only what remains", async () => {
      // GIVEN
      applyRangeChanges.mockResolvedValueOnce({ errorMessage: RANGE_REFUSED });
      const component = await renderEditForm();
      await component.getByRole("textbox", { name: "Weight" }).nth(0).fill("20");
      await component.getByRole("button", { name: "Remove range" }).nth(2).click();
      await component.getByRole("button", { name: "Add range" }).click();
      await component.getByRole("textbox", { name: "Start" }).nth(2).fill("800");
      await component.getByRole("textbox", { name: "End" }).nth(2).fill("899");
      vi.mocked(getNumberPoolForEditing).mockResolvedValue({
        ...poolWithRanges,
        ranges: [
          { id: "range-2", start: 300, end: 399, weight: null },
          { id: "range-1", start: 100, end: 199, weight: 20 },
        ],
      });
      await component.getByRole("button", { name: "Save" }).click();
      await expect.element(component.getByText(RANGE_REFUSED)).toBeVisible();
      expect(component.getByText(RANGE_REFUSED).elements()).toHaveLength(1);
      await expect
        .element(component.getByRole("textbox", { name: "Start" }).nth(2))
        .toHaveValue("800");

      // WHEN
      await component.getByRole("button", { name: "Save" }).click();

      // THEN
      await expect.poll(() => onSuccess).toHaveBeenCalled();
      expect(applyRangeChanges).toHaveBeenLastCalledWith({
        poolId: "pool-1",
        changes: {
          deletes: [],
          smaller: [],
          larger: [],
          creates: [{ start: 800, end: 899, weight: null }],
        },
      });
    });

    test("a refused delete of a range that no longer exists is reported, and the next save sends no range call", async () => {
      // GIVEN
      const RANGE_MISSING = "Unable to find the range range-3";
      applyRangeChanges.mockResolvedValueOnce({ errorMessage: RANGE_MISSING });
      const component = await renderEditForm();
      await component.getByRole("button", { name: "Remove range" }).nth(2).click();
      vi.mocked(getNumberPoolForEditing).mockResolvedValue({
        ...poolWithRanges,
        ranges: poolWithRanges.ranges.filter(({ id }) => id !== "range-3"),
      });
      await component.getByRole("button", { name: "Save" }).click();
      await expect.element(component.getByText(RANGE_MISSING)).toBeVisible();

      // WHEN
      await component.getByRole("button", { name: "Save" }).click();

      // THEN
      await expect.poll(() => onSuccess).toHaveBeenCalled();
      expect(applyRangeChanges).toHaveBeenCalledTimes(1);
      expect(applyRangeChanges).toHaveBeenCalledWith({
        poolId: "pool-1",
        changes: { deletes: ["range-3"], smaller: [], larger: [], creates: [] },
      });
    });
  });

  describe("edit a pool defined in the schema", () => {
    const schemaPool: NumberPoolForEditing = {
      ...storedPool,
      poolType: "Schema",
      ranges: [{ id: "range-1", start: 1000, end: 1999, weight: null }],
    };
    const currentObject = { id: "pool-1" } as NonNullable<
      Parameters<typeof NumberPoolForm>[0]["currentObject"]
    >;

    test("shows the ranges as read-only text with where to change them", async () => {
      // GIVEN
      vi.mocked(getNumberPoolForEditing).mockResolvedValue(schemaPool);

      // WHEN
      const component = await render(<NumberPoolForm currentObject={currentObject} />);

      // THEN
      await expect.element(component.getByText("1,000 – 1,999")).toBeVisible();
      await expect
        .element(component.getByText(/update the schema on the default branch/))
        .toBeVisible();
      expect(component.getByRole("textbox", { name: "Start" }).elements()).toHaveLength(0);
      await expect.element(component.getByLabelText("Name *")).toBeEnabled();
    });

    test("saving a renamed pool updates the pool and sends no range call", async () => {
      // GIVEN
      vi.mocked(getNumberPoolForEditing).mockResolvedValue(schemaPool);
      const component = await render(
        <NumberPoolForm currentObject={currentObject} onSuccess={onSuccess} />
      );
      await component.getByLabelText("Name *").fill("Renamed pool");

      // WHEN
      await component.getByRole("button", { name: "Save" }).click();

      // THEN
      await expect.poll(() => onSuccess).toHaveBeenCalled();
      expect(updatePool).toHaveBeenCalledWith({
        objectKind: "CoreNumberPool",
        data: { id: "pool-1", name: { value: "Renamed pool" } },
      });
      expect(applyRangeChanges).not.toHaveBeenCalled();
    });
  });
});
