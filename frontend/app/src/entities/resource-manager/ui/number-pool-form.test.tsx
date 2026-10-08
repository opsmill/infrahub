import { useQueryClient } from "@tanstack/react-query";
import { afterAll, beforeAll, beforeEach, describe, expect, test, vi } from "vitest";

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
  attributes: [
    generateAttributeSchema({ name: "speed", label: "Speed", kind: "Number" }),
    generateAttributeSchema({
      name: "mtu",
      label: "MTU",
      kind: "Number",
      parameters: { min_value: 150, max_value: 250 },
    }),
  ],
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
  ranges: [{ id: "range-1", start: 100n, end: 199n, weight: 10 }],
};

const RANGE_REFUSED = "Range 300-399 overlaps another range";
const RANGE_MISSING = "Unable to find the range range-3";
const POOL_UNREADABLE = "The number pool could not be read. It may have been deleted.";

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
    vi.resetAllMocks();
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

  async function renderFilledCreateForm() {
    const component = await render(<NumberPoolForm onSuccess={onSuccess} />);
    await component.getByLabelText("Name *").fill("VLAN pool");
    await component.getByRole("combobox", { name: "Node *" }).click();
    await component.getByRole("option", { name: "Interface Infra" }).click();
    await component.getByRole("combobox", { name: "Attribute *" }).click();
    await component.getByRole("option", { name: "Speed" }).click();
    await component.getByRole("textbox", { name: "Start, range 1" }).fill("100");
    await component.getByRole("textbox", { name: "End, range 1" }).fill("199");
    await component.getByRole("textbox", { name: "Weight, range 1" }).fill("10");
    await component.getByRole("button", { name: "Add range" }).click();
    await component.getByRole("textbox", { name: "Start, range 2" }).fill("300");
    await component.getByRole("textbox", { name: "End, range 2" }).fill("399");
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
          { start: 100n, end: 199n, weight: 10 },
          { start: 300n, end: 399n, weight: null },
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

  async function renderCreateFormWithAttribute(attributeLabel: string) {
    const component = await render(<NumberPoolForm onSuccess={onSuccess} />);
    await component.getByRole("combobox", { name: "Node *" }).click();
    await component.getByRole("option", { name: "Interface Infra" }).click();
    await component.getByRole("combobox", { name: "Attribute *" }).click();
    await component.getByRole("option", { name: attributeLabel }).click();
    return component;
  }

  test("shows how the limits of the chosen attribute clip a range", async () => {
    // GIVEN
    const component = await renderCreateFormWithAttribute("MTU");
    await component.getByRole("textbox", { name: "Start, range 1" }).fill("100");

    // WHEN
    await component.getByRole("textbox", { name: "End, range 1" }).fill("199");

    // THEN
    await expect
      .element(component.getByText("Clipped to 150 – 199 by the mtu limits"))
      .toBeVisible();
  });

  test("removes the clip hint when the chosen attribute has no limits", async () => {
    // GIVEN
    const component = await renderCreateFormWithAttribute("MTU");
    await component.getByRole("textbox", { name: "Start, range 1" }).fill("100");
    await component.getByRole("textbox", { name: "End, range 1" }).fill("199");
    await component.getByRole("combobox", { name: "Attribute *" }).click();

    // WHEN
    await component.getByRole("option", { name: "Speed" }).click();

    // THEN
    await expect
      .element(component.getByRole("combobox", { name: "Attribute *" }))
      .toHaveTextContent("Speed");
    await expect.element(component.getByText(/^Clipped to/)).not.toBeInTheDocument();
  });

  test("shows Required on an empty start and does not save", async () => {
    // GIVEN
    const component = await renderFilledCreateForm();
    await component.getByRole("textbox", { name: "Start, range 1" }).fill("");

    // WHEN
    await component.getByRole("button", { name: "Save" }).click();

    // THEN
    await expect.element(component.getByRole("alert")).toHaveTextContent("Required");
    expect(createPool).not.toHaveBeenCalled();
    expect(applyRangeChanges).not.toHaveBeenCalled();
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
    const allocates = component.getByRole("group", { name: "What it allocates" });
    await expect.element(allocates.getByText("Interface Infra")).toBeVisible();
    await expect.element(allocates.getByText("Speed")).toBeVisible();
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
        creates: [{ start: 300n, end: 399n, weight: null }],
      },
    });
  });

  test("saving a renamed pool after a range refusal updates the created pool before its ranges", async () => {
    // GIVEN
    const renamedPool = { ...createdPool, display_label: "Renamed pool" };
    updatePool.mockResolvedValue(renamedPool);
    applyRangeChanges.mockResolvedValueOnce({ errorMessage: RANGE_REFUSED });
    const component = await renderFilledCreateForm();
    await component.getByRole("button", { name: "Save" }).click();
    await expect.element(component.getByText(RANGE_REFUSED)).toBeVisible();
    await component.getByLabelText("Name *").fill("Renamed pool");

    // WHEN
    await component.getByRole("button", { name: "Save" }).click();

    // THEN
    await expect.poll(() => onSuccess).toHaveBeenCalledWith(renamedPool);
    expect(updatePool).toHaveBeenCalledWith({
      objectKind: "CoreNumberPool",
      data: { id: "pool-1", name: { value: "Renamed pool" } },
    });
    expect(updatePool.mock.invocationCallOrder[0]).toBeLessThan(
      applyRangeChanges.mock.invocationCallOrder[1]!
    );
    expect(createPool).toHaveBeenCalledTimes(1);
  });

  test("keeps the form open with the rows as typed when the pool cannot be reloaded after a range refusal", async () => {
    // GIVEN
    applyRangeChanges.mockResolvedValueOnce({ errorMessage: RANGE_REFUSED });
    vi.mocked(getNumberPoolForEditing).mockRejectedValueOnce(new Error("Network error"));
    const component = await renderFilledCreateForm();

    // WHEN
    await component.getByRole("button", { name: "Save" }).click();

    // THEN
    await expect.element(component.getByText(RANGE_REFUSED)).toBeVisible();
    await expect
      .element(component.getByRole("textbox", { name: "Start" }).nth(1))
      .toHaveValue("300");
    expect(onSuccess).not.toHaveBeenCalled();
  });

  test("saving again after a failed reload does not create the range that was already created", async () => {
    // GIVEN
    applyRangeChanges.mockResolvedValueOnce({ errorMessage: RANGE_REFUSED });
    vi.mocked(getNumberPoolForEditing).mockRejectedValueOnce(new Error("Network error"));
    const component = await renderFilledCreateForm();
    await component.getByRole("button", { name: "Save" }).click();
    await expect.element(component.getByText(RANGE_REFUSED)).toBeVisible();

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
        creates: [{ start: 300n, end: 399n, weight: null }],
      },
    });
  });

  describe("edit", () => {
    const poolWithRanges: NumberPoolForEditing = {
      ...storedPool,
      ranges: [
        { id: "range-3", start: 600n, end: 699n, weight: null },
        { id: "range-2", start: 300n, end: 399n, weight: null },
        { id: "range-1", start: 100n, end: 199n, weight: 10 },
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
      const allocates = component.getByRole("group", { name: "What it allocates" });
      await expect.element(allocates.getByText("Interface Infra")).toBeVisible();
      await expect.element(allocates.getByText("Speed")).toBeVisible();
      await expect.element(allocates.getByText("Not scoped")).toBeVisible();
      const starts = component.getByRole("textbox", { name: "Start" });
      await expect.element(starts.nth(0)).toHaveValue("100");
      await expect.element(starts.nth(1)).toHaveValue("300");
      await expect.element(starts.nth(2)).toHaveValue("600");
      expect(component.getByRole("combobox", { name: "Node *" }).elements()).toHaveLength(0);
    });

    test("reopening the form lists the stored ranges read again, not the ranges from the last opening", async () => {
      // GIVEN
      const component = await renderEditForm();
      await component.rerender(<div />);
      vi.mocked(getNumberPoolForEditing).mockResolvedValue(storedPool);

      // WHEN
      await component.rerender(<NumberPoolForm currentObject={currentObject} />);

      // THEN
      await expect
        .poll(() => component.getByRole("textbox", { name: "Start" }).elements())
        .toHaveLength(1);
      await expect.element(component.getByRole("textbox", { name: "Start" })).toHaveValue("100");
    });

    test("keeps the typed rows open when a background reload of the pool fails", async () => {
      // GIVEN
      const RefetchButton = () => {
        const queryClient = useQueryClient();
        return (
          <button type="button" onClick={() => queryClient.invalidateQueries()}>
            Reload
          </button>
        );
      };
      vi.mocked(getNumberPoolForEditing).mockResolvedValue(poolWithRanges);
      const component = await render(
        <>
          <NumberPoolForm currentObject={currentObject} />
          <RefetchButton />
        </>
      );
      await component.getByRole("textbox", { name: "End" }).first().fill("150");
      vi.mocked(getNumberPoolForEditing).mockRejectedValue(new Error("network down"));

      // WHEN
      await component.getByRole("button", { name: "Reload" }).click();

      // THEN
      await expect
        .poll(() => vi.mocked(getNumberPoolForEditing).mock.calls.length)
        .toBeGreaterThan(1);
      await expect
        .element(component.getByRole("textbox", { name: "End" }).first())
        .toHaveValue("150");
      expect(component.getByText("Unable to load the number pool").elements()).toHaveLength(0);
    });

    test("shows the load error instead of the cached rows when the first read after opening fails", async () => {
      // GIVEN
      const component = await renderEditForm();
      await component.rerender(<div />);
      vi.mocked(getNumberPoolForEditing).mockRejectedValue(new Error("network down"));

      // WHEN
      await component.rerender(<NumberPoolForm currentObject={currentObject} />);

      // THEN
      await expect.element(component.getByText("Unable to load the number pool")).toBeVisible();
      expect(component.getByRole("textbox", { name: "Start" }).elements()).toHaveLength(0);
    });

    test("keeps the form open with the rows as typed and reports a pool that can no longer be read when saving", async () => {
      // GIVEN
      const component = await renderEditForm();
      await component.getByRole("textbox", { name: "End" }).first().fill("150");
      vi.mocked(getNumberPoolForEditing).mockRejectedValue(
        new Error("Number pool pool-1 not found")
      );

      // WHEN
      await component.getByRole("button", { name: "Save" }).click();

      // THEN
      await expect.element(component.getByText(POOL_UNREADABLE)).toBeVisible();
      await expect
        .element(component.getByRole("textbox", { name: "End" }).first())
        .toHaveValue("150");
      expect(onSuccess).not.toHaveBeenCalled();
      expect(updatePool).not.toHaveBeenCalled();
      expect(applyRangeChanges).not.toHaveBeenCalled();
    });

    test("shows only the pool read failure when saving again after a range refusal", async () => {
      // GIVEN
      applyRangeChanges.mockResolvedValueOnce({ errorMessage: RANGE_REFUSED });
      const component = await renderEditForm();
      await component.getByRole("textbox", { name: "End" }).first().fill("150");
      await component.getByRole("button", { name: "Save" }).click();
      await expect.element(component.getByText(RANGE_REFUSED)).toBeVisible();
      vi.mocked(getNumberPoolForEditing).mockRejectedValue(
        new Error("Number pool pool-1 not found")
      );

      // WHEN
      await component.getByRole("button", { name: "Save" }).click();

      // THEN
      await expect.element(component.getByText(POOL_UNREADABLE)).toBeVisible();
      await expect.element(component.getByText(RANGE_REFUSED)).not.toBeInTheDocument();
    });

    test("no longer shows a range refusal once a later save is refused for the pool itself", async () => {
      // GIVEN
      applyRangeChanges.mockResolvedValueOnce({ errorMessage: RANGE_REFUSED });
      const component = await renderEditForm();
      await component.getByRole("textbox", { name: "End" }).first().fill("150");
      await component.getByRole("button", { name: "Save" }).click();
      await expect.element(component.getByText(RANGE_REFUSED)).toBeVisible();
      await component.getByLabelText("Name *").fill("Renamed pool");
      updatePool.mockRejectedValue(new Error("Name already used"));

      // WHEN
      await component.getByRole("button", { name: "Save" }).click();

      // THEN
      await expect.poll(() => updatePool).toHaveBeenCalled();
      await expect.element(component.getByText(RANGE_REFUSED)).not.toBeInTheDocument();
      expect(onSuccess).not.toHaveBeenCalled();
    });

    test("keeps a range added elsewhere after the form loaded when saving", async () => {
      // GIVEN
      const component = await renderEditForm();
      vi.mocked(getNumberPoolForEditing).mockResolvedValue({
        ...poolWithRanges,
        ranges: [...poolWithRanges.ranges, { id: "range-9", start: 900n, end: 999n, weight: null }],
      });

      // WHEN
      await component.getByRole("button", { name: "Save" }).click();

      // THEN
      await expect.poll(() => onSuccess).toHaveBeenCalled();
      expect(applyRangeChanges).not.toHaveBeenCalled();
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

    test("loads a range ending above 2^53 exactly and saves it unchanged without a range call", async () => {
      // GIVEN
      vi.mocked(getNumberPoolForEditing).mockResolvedValue({
        ...storedPool,
        ranges: [{ id: "range-1", start: 1n, end: 9223372036854775807n, weight: null }],
      });
      const component = await render(
        <NumberPoolForm currentObject={currentObject} onSuccess={onSuccess} />
      );
      await expect
        .element(component.getByRole("textbox", { name: "End, range 1" }))
        .toHaveValue("9223372036854775807");

      // WHEN
      await component.getByRole("button", { name: "Save" }).click();

      // THEN
      await expect.poll(() => onSuccess).toHaveBeenCalled();
      expect(component.getByRole("alert").elements()).toHaveLength(0);
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
          smaller: [{ id: "range-1", start: 100n, end: 150n, weight: 10 }],
          larger: [{ id: "range-2", start: 300n, end: 450n, weight: null }],
          creates: [{ start: 800n, end: 899n, weight: null }],
        },
      });
    });

    test("compares the rows with the ranges as stored when saving, not as first loaded", async () => {
      // GIVEN
      const component = await renderEditForm();
      vi.mocked(getNumberPoolForEditing).mockResolvedValue({
        ...poolWithRanges,
        ranges: poolWithRanges.ranges.map((range) =>
          range.id === "range-1" ? { ...range, weight: 20 } : range
        ),
      });

      // WHEN
      await component.getByRole("button", { name: "Save" }).click();

      // THEN
      await expect.poll(() => onSuccess).toHaveBeenCalled();
      expect(applyRangeChanges).toHaveBeenCalledWith({
        poolId: "pool-1",
        changes: {
          deletes: [],
          smaller: [{ id: "range-1", start: 100n, end: 199n, weight: 10 }],
          larger: [],
          creates: [],
        },
      });
    });

    async function renderEditFormWithMidSequenceRefusal() {
      applyRangeChanges.mockResolvedValueOnce({ errorMessage: RANGE_REFUSED });
      const component = await renderEditForm();
      await component.getByRole("textbox", { name: "Weight, range 1" }).fill("20");
      await component.getByRole("button", { name: "Remove range 3" }).click();
      await component.getByRole("button", { name: "Add range" }).click();
      await component.getByRole("textbox", { name: "Start, range 3" }).fill("800");
      await component.getByRole("textbox", { name: "End, range 3" }).fill("899");
      vi.mocked(getNumberPoolForEditing)
        .mockResolvedValueOnce(poolWithRanges)
        .mockResolvedValue({
          ...poolWithRanges,
          ranges: [
            { id: "range-2", start: 300n, end: 399n, weight: null },
            { id: "range-1", start: 100n, end: 199n, weight: 20 },
          ],
        });
      return component;
    }

    async function renderEditFormWithRefusedDelete() {
      applyRangeChanges.mockResolvedValueOnce({ errorMessage: RANGE_MISSING });
      const component = await renderEditForm();
      await component.getByRole("button", { name: "Remove range 3" }).click();
      vi.mocked(getNumberPoolForEditing)
        .mockResolvedValueOnce(poolWithRanges)
        .mockResolvedValue({
          ...poolWithRanges,
          ranges: poolWithRanges.ranges.filter(({ id }) => id !== "range-3"),
        });
      return component;
    }

    test("after a refusal mid-sequence, keeps the rows as typed and shows the refusal once", async () => {
      // GIVEN
      const component = await renderEditFormWithMidSequenceRefusal();

      // WHEN
      await component.getByRole("button", { name: "Save" }).click();

      // THEN
      await expect.element(component.getByText(RANGE_REFUSED)).toBeVisible();
      expect(component.getByText(RANGE_REFUSED).elements()).toHaveLength(1);
      await expect
        .element(component.getByRole("textbox", { name: "Start, range 3" }))
        .toHaveValue("800");
      expect(onSuccess).not.toHaveBeenCalled();
    });

    test("after a refusal mid-sequence, the next save sends only what remains", async () => {
      // GIVEN
      const component = await renderEditFormWithMidSequenceRefusal();
      await component.getByRole("button", { name: "Save" }).click();
      await expect.element(component.getByText(RANGE_REFUSED)).toBeVisible();

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
          creates: [{ start: 800n, end: 899n, weight: null }],
        },
      });
    });

    test("reports a refused delete of a range that no longer exists", async () => {
      // GIVEN
      const component = await renderEditFormWithRefusedDelete();

      // WHEN
      await component.getByRole("button", { name: "Save" }).click();

      // THEN
      await expect.element(component.getByText(RANGE_MISSING)).toBeVisible();
      expect(applyRangeChanges).toHaveBeenCalledWith({
        poolId: "pool-1",
        changes: { deletes: ["range-3"], smaller: [], larger: [], creates: [] },
      });
    });

    test("after a refused delete of a range that no longer exists, the next save sends no range call", async () => {
      // GIVEN
      const component = await renderEditFormWithRefusedDelete();
      await component.getByRole("button", { name: "Save" }).click();
      await expect.element(component.getByText(RANGE_MISSING)).toBeVisible();

      // WHEN
      await component.getByRole("button", { name: "Save" }).click();

      // THEN
      await expect.poll(() => onSuccess).toHaveBeenCalled();
      expect(applyRangeChanges).toHaveBeenCalledTimes(1);
    });

    test("appends a range the user adds after the stored ranges sorted by weight", async () => {
      // GIVEN
      const component = await renderEditForm();

      // WHEN
      await component.getByRole("button", { name: "Add range" }).click();

      // THEN
      await expect
        .element(component.getByRole("textbox", { name: "Start, range 3" }))
        .toHaveValue("600");
      await expect
        .element(component.getByRole("textbox", { name: "Start, range 4" }))
        .toHaveValue("");
    });
  });

  describe("edit a pool defined in the schema", () => {
    const schemaPool: NumberPoolForEditing = {
      ...storedPool,
      poolType: "Schema",
      ranges: [{ id: "range-1", start: 1000n, end: 1999n, weight: null }],
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
