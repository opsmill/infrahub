import { beforeEach, describe, expect, test } from "vitest";

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

const schemaWithoutDefaultSort = generateNodeSchema({ ...schema, order_by: [] });

const seedSortInUrl = (sort: string) =>
  window.history.replaceState(null, "", `${window.location.pathname}?sort=${sort}`);

describe("SortEditor", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", window.location.pathname);
  });

  test("hides the schema default sort fields from the picker", async () => {
    // GIVEN
    const component = await render(<SortEditor schema={schema} />);

    // WHEN
    await component.getByRole("button", { name: "Add sort" }).click();

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Description" })).toBeVisible();
    await expect.element(component.getByRole("menuitem", { name: "Name" })).not.toBeInTheDocument();
  });

  test("shows the schema default as an applied, non-removable row", async () => {
    // GIVEN
    const component = await render(<SortEditor schema={schema} />);

    // THEN
    await expect.element(component.getByText("Default order · applied now")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Name Sort field" })).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Sort direction" }))
      .toHaveTextContent("Ascending");
    await expect
      .element(component.getByRole("button", { name: "Why this sort can't be removed" }))
      .toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Remove sort" }))
      .not.toBeInTheDocument();
  });

  test("changes the sort field from a row", async () => {
    // GIVEN
    const component = await render(<SortEditor schema={schema} />);

    // WHEN
    await component.getByRole("button", { name: "Name Sort field" }).click();
    await component.getByRole("option", { name: "Description" }).click();

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Description Sort field" }))
      .toBeVisible();
  });

  test("renders only the field picker when there is no sort to edit", async () => {
    // GIVEN
    const component = await render(<SortEditor schema={schemaWithoutDefaultSort} />);

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Name" })).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Add sort" }))
      .not.toBeInTheDocument();
  });

  test("switches to a custom order when changing the direction", async () => {
    // GIVEN
    const component = await render(<SortEditor schema={schema} />);

    // WHEN
    await component.getByRole("button", { name: "Sort direction" }).click();
    await component.getByRole("option", { name: "Descending" }).click();

    // THEN
    await expect.element(component.getByText("Custom order")).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Sort direction" }))
      .toHaveTextContent("Descending");
  });

  test("resets a custom order back to the default", async () => {
    // GIVEN
    seedSortInUrl("name__value__desc");
    const component = await render(<SortEditor schema={schema} />);

    // WHEN
    await component.getByRole("button", { name: "Reset to default" }).first().click();

    // THEN
    await expect.element(component.getByText("Default order · applied now")).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Sort direction" }))
      .toHaveTextContent("Ascending");
  });

  test("offers to clear the sort instead of resetting when the schema has no default", async () => {
    // GIVEN
    seedSortInUrl("name__value__desc");
    const component = await render(<SortEditor schema={schemaWithoutDefaultSort} />);

    // THEN
    await expect.element(component.getByText("Custom order")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Clear sort" })).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Reset to default" }))
      .not.toBeInTheDocument();
  });

  test("clears the custom sort back to the field picker when the schema has no default", async () => {
    // GIVEN
    seedSortInUrl("name__value__desc");
    const component = await render(<SortEditor schema={schemaWithoutDefaultSort} />);

    // WHEN
    await component.getByRole("button", { name: "Clear sort" }).click();

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Name" })).toBeVisible();
  });

  test("adds a sort as a new row", async () => {
    // GIVEN
    const component = await render(<SortEditor schema={schema} />);

    // WHEN
    await component.getByRole("button", { name: "Add sort" }).click();
    await component.getByRole("menuitem", { name: "Description" }).click();
    await component.getByRole("menuitem", { name: "Descending" }).click();

    // THEN
    await expect.element(component.getByText("Custom order")).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Description Sort field" }))
      .toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Descending Sort direction" }))
      .toBeVisible();
  });

  test("excludes fields used by other rows from a row's field select", async () => {
    // GIVEN
    seedSortInUrl("name__value__asc,description__value__desc");
    const component = await render(<SortEditor schema={schema} />);

    // WHEN
    await component.getByRole("button", { name: "Name Sort field" }).click();

    // THEN
    await expect.element(component.getByRole("option", { name: "Name" })).toBeVisible();
    await expect
      .element(component.getByRole("option", { name: "Description" }))
      .not.toBeInTheDocument();
  });

  test("removes one row of a multi-row custom sort", async () => {
    // GIVEN
    seedSortInUrl("name__value__asc,description__value__desc");
    const component = await render(<SortEditor schema={schema} />);

    // WHEN
    await component.getByRole("button", { name: "Remove sort" }).first().click();

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Name Sort field" }))
      .not.toBeInTheDocument();
    await expect
      .element(component.getByRole("button", { name: "Description Sort field" }))
      .toBeVisible();
  });

  test("frames removing the last custom row as a reset to the default", async () => {
    // GIVEN
    seedSortInUrl("description__value__desc");
    const component = await render(<SortEditor schema={schema} />);

    // WHEN
    await component.getByRole("button", { name: "Reset to default" }).nth(1).click();

    // THEN
    await expect.element(component.getByText("Default order · applied now")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Name Sort field" })).toBeVisible();
  });
});
