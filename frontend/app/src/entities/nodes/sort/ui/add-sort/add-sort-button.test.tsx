import { describe, expect, test, vi } from "vitest";

import type { SortField } from "@/entities/nodes/sort/domain/model/sort";

import { render } from "../../../../../../tests/components/render";
import { initPointerTracking } from "../../../../../../tests/components/utils";
import { generateAttributeSchema, generateNodeSchema } from "../../../../../../tests/fake/schema";
import { AddSortButton } from "./add-sort-button";

const schema = generateNodeSchema({
  attributes: [
    generateAttributeSchema({ name: "name", label: "Name", kind: "Text" }),
    generateAttributeSchema({ name: "description", label: "Description", kind: "Text" }),
  ],
  relationships: [],
});

const ALL_SORTABLE_FIELDS = new Set<SortField>([
  "name__value",
  "description__value",
  "node_metadata__created_at",
  "node_metadata__updated_at",
]);

describe("AddSortButton", () => {
  test("opens the picker and forwards the selected sort", async () => {
    // GIVEN
    const onSelect = vi.fn();
    const component = await render(<AddSortButton schema={schema} onSelect={onSelect} />);

    // WHEN
    await component.getByRole("button", { name: "Add sort" }).click();
    await component.getByRole("menuitem", { name: "Name" }).click();
    await component.getByRole("menuitem", { name: "Ascending" }).click();

    // THEN
    expect(onSelect).toHaveBeenCalledWith({ field: "name__value", direction: "ASC" });
  });

  test("hides fields that are already in use from the picker", async () => {
    // GIVEN
    const component = await render(
      <AddSortButton
        schema={schema}
        activeFields={new Set<SortField>(["name__value"])}
        onSelect={vi.fn()}
      />
    );

    // WHEN
    await component.getByRole("button", { name: "Add sort" }).click();

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Description" })).toBeVisible();
    await expect.element(component.getByRole("menuitem", { name: "Name" })).not.toBeInTheDocument();
  });

  test("disables the button with an explanatory tooltip when every sortable field is in use", async () => {
    // GIVEN
    const component = await render(
      <AddSortButton schema={schema} activeFields={ALL_SORTABLE_FIELDS} onSelect={vi.fn()} />
    );

    // WHEN
    await initPointerTracking(component.locator);
    await component.getByRole("button", { name: "Add sort" }).hover();

    // THEN
    await expect.element(component.getByRole("button", { name: "Add sort" })).toBeDisabled();
    await expect
      .element(component.getByRole("tooltip", { name: "All fields are already in use." }))
      .toBeVisible();
  });
});
