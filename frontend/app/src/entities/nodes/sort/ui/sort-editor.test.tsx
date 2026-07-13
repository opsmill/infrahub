import { describe, expect, test } from "vitest";

import { render } from "../../../../../tests/components/render";
import { generateAttributeSchema, generateNodeSchema } from "../../../../../tests/fake/schema";
import { SortEditor } from "./sort-editor";

const schema = generateNodeSchema({
  order_by: ["name__value"],
  attributes: [
    generateAttributeSchema({ name: "name", label: "Name", kind: "Text" }),
    generateAttributeSchema({ name: "description", label: "Description", kind: "Text" }),
  ],
  relationships: [],
});

describe("SortEditor", () => {
  test("hides the schema default sort fields from the picker", async () => {
    // GIVEN
    const component = await render(<SortEditor schema={schema} />);

    // WHEN
    await component.getByRole("button", { name: "Add sort" }).click();

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Description" })).toBeVisible();
    await expect.element(component.getByRole("menuitem", { name: "Name" })).not.toBeInTheDocument();
  });

  test("shows the schema default sort as a row", async () => {
    // GIVEN
    const component = await render(<SortEditor schema={schema} />);

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Name", exact: true }))
      .toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Sort direction for Name" }))
      .toHaveTextContent("Ascending");
  });

  test("blocks removing the only row while on the schema default", async () => {
    // GIVEN
    const component = await render(<SortEditor schema={schema} />);

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Why this sort can't be removed" }))
      .toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Remove sort" }))
      .not.toBeInTheDocument();
  });

  test("changes the sort direction from a row", async () => {
    // GIVEN
    const component = await render(<SortEditor schema={schema} />);

    // WHEN
    await component.getByRole("button", { name: "Sort direction for Name" }).click();
    await component.getByRole("option", { name: "Descending" }).click();

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Sort direction for Name" }))
      .toHaveTextContent("Descending");
  });

  test("changes the sort field from a row", async () => {
    // GIVEN
    const component = await render(<SortEditor schema={schema} />);

    // WHEN
    await component.getByRole("button", { name: "Name", exact: true }).click();
    await component.getByRole("menuitemradio", { name: "Description" }).click();

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Description", exact: true }))
      .toBeVisible();
  });
});
