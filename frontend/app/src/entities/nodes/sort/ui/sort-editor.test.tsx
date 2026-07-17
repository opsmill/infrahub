import { beforeEach, describe, expect, test } from "vitest";

import { render } from "../../../../../tests/components/render";
import { generateAttributeSchema, generateNodeSchema } from "../../../../../tests/fake/schema";
import { SortEditor } from "./sort-editor";
import { PEER_LABEL_SEPARATOR } from "./sort-options";

const schemaWithDefaultSort = generateNodeSchema({
  order_by: ["name__value"],
  attributes: [
    generateAttributeSchema({ name: "name", label: "Name", kind: "Text" }),
    generateAttributeSchema({ name: "description", label: "Description", kind: "Text" }),
  ],
  relationships: [],
});

const schemaWithoutDefaultSort = generateNodeSchema({ ...schemaWithDefaultSort, order_by: [] });

const seedSortInUrl = (sort: string) =>
  window.history.replaceState(null, "", `${window.location.pathname}?sort=${sort}`);

describe("SortEditor", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", window.location.pathname);
  });

  test("hides the schema default sort fields from the picker", async () => {
    // GIVEN
    const component = await render(<SortEditor schema={schemaWithDefaultSort} />);

    // WHEN
    await component.getByRole("button", { name: "Add sort" }).click();

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Description" })).toBeVisible();
    await expect.element(component.getByRole("menuitem", { name: "Name" })).not.toBeInTheDocument();
  });

  test("shows the schema default as an applied, non-removable row", async () => {
    // GIVEN
    const schema = schemaWithDefaultSort;

    // WHEN
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

  // A schema's default order can target an attribute sub-property the picker never offers as a
  // selectable field (it only builds `__value` fields): IP prefixes/addresses sort on
  // `prefix__version`, dropdowns can sort on `status__label`, etc. Without a read-only fallback the
  // row's field select has no matching option and renders blank.
  test.each([
    {
      kind: "IPNetwork",
      attribute: "prefix",
      label: "Prefix",
      field: "prefix__version",
      property: "version",
    },
    {
      kind: "IPNetwork",
      attribute: "prefix",
      label: "Prefix",
      field: "prefix__binary_address",
      property: "binary address",
    },
    {
      kind: "MacAddress",
      attribute: "mac",
      label: "Mac",
      field: "mac__dot_notation",
      property: "dot notation",
    },
    {
      kind: "Dropdown",
      attribute: "status",
      label: "Status",
      field: "status__label",
      property: "label",
    },
  ])("labels the read-only $field sub-property sort", async ({
    kind,
    attribute,
    label,
    field,
    property,
  }) => {
    // GIVEN
    const schema = generateNodeSchema({
      order_by: [field],
      attributes: [generateAttributeSchema({ name: attribute, label, kind })],
      relationships: [],
    });
    const expectedLabel = `${label}${PEER_LABEL_SEPARATOR}${property}`;

    // WHEN
    const component = await render(<SortEditor schema={schema} />);

    // THEN
    await expect
      .element(component.getByRole("button", { name: `${expectedLabel} Sort field` }))
      .toBeVisible();
  });

  test("changes the sort field from a row", async () => {
    // GIVEN
    const component = await render(<SortEditor schema={schemaWithDefaultSort} />);

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
    const schema = schemaWithoutDefaultSort;

    // WHEN
    const component = await render(<SortEditor schema={schema} />);

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Name" })).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Add sort" }))
      .not.toBeInTheDocument();
  });

  test("switches to a custom order when changing the direction", async () => {
    // GIVEN
    const component = await render(<SortEditor schema={schemaWithDefaultSort} />);

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
    const component = await render(<SortEditor schema={schemaWithDefaultSort} />);

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

    // WHEN
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
    const component = await render(<SortEditor schema={schemaWithDefaultSort} />);

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
    const component = await render(<SortEditor schema={schemaWithDefaultSort} />);

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
    const component = await render(<SortEditor schema={schemaWithDefaultSort} />);

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
    const component = await render(<SortEditor schema={schemaWithDefaultSort} />);

    // WHEN
    await component.getByRole("button", { name: "Reset to default" }).nth(1).click();

    // THEN
    await expect.element(component.getByText("Default order · applied now")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Name Sort field" })).toBeVisible();
  });
});
