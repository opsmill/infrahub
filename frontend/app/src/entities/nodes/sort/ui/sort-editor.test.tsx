import { beforeEach, describe, expect, test } from "vitest";

import type { SortField } from "@/entities/nodes/sort/domain/model/sort";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

import { render } from "../../../../../tests/components/render";
import { generateAttributeSchema, generateNodeSchema } from "../../../../../tests/fake/schema";
import { describeUnlistedSortField, SortEditor } from "./sort-editor";
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
  ])(
    "labels the read-only $field sub-property sort",
    async ({ kind, attribute, label, field, property }) => {
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
    }
  );

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

describe("describeUnlistedSortField", () => {
  // --- Resolving the attribute label ---

  test("labels a sub-property sort using the attribute's schema label", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [generateAttributeSchema({ name: "prefix", label: "Prefix", kind: "IPNetwork" })],
    });

    // WHEN
    const label = describeUnlistedSortField("prefix__version", schema);

    // THEN
    expect(label).toBe(`Prefix${PEER_LABEL_SEPARATOR}version`);
  });

  test("selects the attribute matching the field's attribute name among several", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({ name: "prefix", label: "Prefix", kind: "IPNetwork" }),
        generateAttributeSchema({ name: "gateway", label: "Gateway", kind: "IPHost" }),
      ],
    });

    // WHEN
    const label = describeUnlistedSortField("gateway__version", schema);

    // THEN
    expect(label).toBe(`Gateway${PEER_LABEL_SEPARATOR}version`);
  });

  test("falls back to the raw attribute name when no attribute matches the field", () => {
    // GIVEN
    const schema = generateNodeSchema({ attributes: [] });

    // WHEN
    const label = describeUnlistedSortField("prefix__version", schema);

    // THEN
    expect(label).toBe(`prefix${PEER_LABEL_SEPARATOR}version`);
  });

  test("falls back to the attribute name when the matching attribute has a null label", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [generateAttributeSchema({ name: "prefix", label: null, kind: "IPNetwork" })],
    });

    // WHEN
    const label = describeUnlistedSortField("prefix__version", schema);

    // THEN
    expect(label).toBe(`prefix${PEER_LABEL_SEPARATOR}version`);
  });

  test("keeps an empty-string label instead of the name (nullish coalescing, not falsiness)", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [generateAttributeSchema({ name: "prefix", label: "", kind: "IPNetwork" })],
    });

    // WHEN
    const label = describeUnlistedSortField("prefix__version", schema);

    // THEN
    expect(label).toBe(`${PEER_LABEL_SEPARATOR}version`);
  });

  test("keeps underscores in the attribute name when falling back (only property is humanized)", () => {
    // GIVEN
    const schema = generateNodeSchema({ attributes: [] });

    // WHEN
    const label = describeUnlistedSortField("binary_address__version", schema);

    // THEN
    expect(label).toBe(`binary_address${PEER_LABEL_SEPARATOR}version`);
  });

  test("falls back to the attribute name when the schema has no attributes array", () => {
    // GIVEN
    const schema = { ...generateNodeSchema(), attributes: undefined } as unknown as ModelSchema;

    // WHEN
    const label = describeUnlistedSortField("prefix__version", schema);

    // THEN
    expect(label).toBe(`prefix${PEER_LABEL_SEPARATOR}version`);
  });

  // --- Humanizing the property segments ---

  test("replaces underscores within a property segment with spaces", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [generateAttributeSchema({ name: "mac", label: "Mac", kind: "MacAddress" })],
    });

    // WHEN
    const label = describeUnlistedSortField("mac__dot_notation", schema);

    // THEN
    expect(label).toBe(`Mac${PEER_LABEL_SEPARATOR}dot notation`);
  });

  test("replaces every underscore in a segment, not just the first", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [generateAttributeSchema({ name: "mac", label: "Mac", kind: "MacAddress" })],
    });

    // WHEN
    const label = describeUnlistedSortField("mac__a_b_c" as SortField, schema);

    // THEN
    expect(label).toBe(`Mac${PEER_LABEL_SEPARATOR}a b c`);
  });

  test("joins multiple property segments with a middle dot", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [generateAttributeSchema({ name: "prefix", label: "Prefix", kind: "IPNetwork" })],
    });

    // WHEN
    const label = describeUnlistedSortField("prefix__a__b" as SortField, schema);

    // THEN
    expect(label).toBe("Prefix › a › b");
  });

  test("humanizes each segment before joining several multi-word segments", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [generateAttributeSchema({ name: "prefix", label: "Prefix", kind: "IPNetwork" })],
    });

    // WHEN
    const label = describeUnlistedSortField("prefix__foo_bar__baz_qux" as SortField, schema);

    // THEN
    expect(label).toBe("Prefix › foo bar › baz qux");
  });

  // --- Degenerate field shapes ---

  test("returns only the attribute label when the field has a trailing empty property", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [generateAttributeSchema({ name: "prefix", label: "Prefix", kind: "IPNetwork" })],
    });

    // WHEN
    const label = describeUnlistedSortField("prefix__" as SortField, schema);

    // THEN
    expect(label).toBe("Prefix");
  });

  test("handles a leading separator that yields an empty attribute name", () => {
    // GIVEN
    const schema = generateNodeSchema({ attributes: [] });

    // WHEN
    const label = describeUnlistedSortField("__version" as SortField, schema);

    // THEN
    expect(label).toBe(`${PEER_LABEL_SEPARATOR}version`);
  });
});
