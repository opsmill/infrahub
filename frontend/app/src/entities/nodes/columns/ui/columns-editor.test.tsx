import { beforeEach, describe, expect, test } from "vitest";

import { RELATIONSHIP_COLUMN_SURFACE } from "@/entities/nodes/columns/domain/model/column-surface";

import { render } from "../../../../../tests/components/render";
import { generateAttributeSchema, generateNodeSchema } from "../../../../../tests/fake/schema";
import { ColumnsEditor } from "./columns-editor";

const objectSchema = generateNodeSchema({
  attributes: [
    generateAttributeSchema({ name: "name", label: "Name", kind: "Text", order_weight: 1000 }),
    generateAttributeSchema({
      name: "description",
      label: "Description",
      kind: "Text",
      order_weight: 2000,
    }),
    generateAttributeSchema({
      name: "internal_note",
      label: "Internal note",
      kind: "Text",
      display: "extra",
      order_weight: 3000,
    }),
  ],
  relationships: [],
});

const seedColumnsInUrl = ({ hidden, shown }: { hidden?: string; shown?: string }) => {
  const search = new URLSearchParams();
  if (hidden) search.set("hide_columns", hidden);
  if (shown) search.set("show_columns", shown);

  window.history.replaceState(null, "", `${window.location.pathname}?${search}`);
};

const seedParamInUrl = (param: string, value: string) =>
  window.history.replaceState(
    null,
    "",
    `${window.location.pathname}?${param}=${encodeURIComponent(value)}`
  );

const getParamInUrl = (param: string) => new URLSearchParams(window.location.search).get(param);
const getHiddenColumnsInUrl = () => getParamInUrl("hide_columns");
const getShownColumnsInUrl = () => getParamInUrl("show_columns");

const countMenuItems = () => document.querySelectorAll('[role="menu"] [role="menuitem"]').length;

describe("ColumnsEditor", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", window.location.pathname);
  });

  test("lists every column the surface can show or hide", async () => {
    // GIVEN
    const schema = objectSchema;

    // WHEN
    const component = await render(<ColumnsEditor schema={schema} />);

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Name" })).toBeVisible();
    await expect.element(component.getByRole("menuitem", { name: "Description" })).toBeVisible();
    await expect.element(component.getByRole("menuitem", { name: "Internal note" })).toBeVisible();
    expect(countMenuItems()).toBe(3);
  });

  test("marks a column the surface shows by default as visible", async () => {
    // GIVEN
    const schema = objectSchema;

    // WHEN
    const component = await render(<ColumnsEditor schema={schema} />);

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "Description" }).getByText("visible"))
      .toBeInTheDocument();
  });

  test("leaves a column the surface hides by default unmarked", async () => {
    // GIVEN
    const schema = objectSchema;

    // WHEN
    const component = await render(<ColumnsEditor schema={schema} />);

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "Internal note" }).getByText("visible"))
      .not.toBeInTheDocument();
  });

  test("hides a default-visible column by naming it in the hide param", async () => {
    // GIVEN
    const component = await render(<ColumnsEditor schema={objectSchema} />);

    // WHEN
    await component.getByRole("menuitem", { name: "Description" }).click();

    // THEN
    await expect.poll(getHiddenColumnsInUrl).toBe("description");
    expect(getShownColumnsInUrl()).toBeNull();
  });

  test("reveals a default-hidden column by naming it in the show param", async () => {
    // GIVEN
    const component = await render(<ColumnsEditor schema={objectSchema} />);

    // WHEN
    await component.getByRole("menuitem", { name: "Internal note" }).click();

    // THEN
    await expect.poll(getShownColumnsInUrl).toBe("internal_note");
    expect(getHiddenColumnsInUrl()).toBeNull();
  });

  test("removes the hide param when showing back the column it just hid", async () => {
    // GIVEN
    seedColumnsInUrl({ hidden: "description" });
    const component = await render(<ColumnsEditor schema={objectSchema} />);

    // WHEN
    await component.getByRole("menuitem", { name: "Description" }).click();

    // THEN
    await expect.poll(getHiddenColumnsInUrl).toBeNull();
  });

  test("removes the show param when hiding back the column it just revealed", async () => {
    // GIVEN
    seedColumnsInUrl({ shown: "internal_note" });
    const component = await render(<ColumnsEditor schema={objectSchema} />);

    // WHEN
    await component.getByRole("menuitem", { name: "Internal note" }).click();

    // THEN
    await expect.poll(getShownColumnsInUrl).toBeNull();
  });

  test("keeps the other hidden column when showing one of two", async () => {
    // GIVEN
    seedColumnsInUrl({ hidden: "name,description" });
    const component = await render(<ColumnsEditor schema={objectSchema} />);

    // WHEN
    await component.getByRole("menuitem", { name: "Description" }).click();

    // THEN
    await expect.poll(getHiddenColumnsInUrl).toBe("name");
  });

  test("leaves an existing sort in the url untouched", async () => {
    // GIVEN
    seedParamInUrl("sort", "name__value__desc");
    const component = await render(<ColumnsEditor schema={objectSchema} />);

    // WHEN
    await component.getByRole("menuitem", { name: "Description" }).click();

    // THEN
    await expect.poll(getHiddenColumnsInUrl).toBe("description");
    expect(getParamInUrl("sort")).toBe("name__value__desc");
  });

  test("leaves an existing pagination in the url untouched", async () => {
    // GIVEN
    seedParamInUrl("pagination", '{"limit":20,"offset":10}');
    const component = await render(<ColumnsEditor schema={objectSchema} />);

    // WHEN
    await component.getByRole("menuitem", { name: "Description" }).click();

    // THEN
    await expect.poll(getHiddenColumnsInUrl).toBe("description");
    expect(getParamInUrl("pagination")).toBe('{"limit":20,"offset":10}');
  });

  test("removes both params when resetting to the surface defaults", async () => {
    // GIVEN
    seedColumnsInUrl({ hidden: "description", shown: "internal_note" });
    const component = await render(<ColumnsEditor schema={objectSchema} />);

    // WHEN
    await component.getByRole("button", { name: "Reset columns" }).click();

    // THEN
    await expect.poll(getHiddenColumnsInUrl).toBeNull();
    await expect.poll(getShownColumnsInUrl).toBeNull();
  });

  test("offers no reset control while the view still shows the surface defaults", async () => {
    // GIVEN
    const schema = objectSchema;

    // WHEN
    const component = await render(<ColumnsEditor schema={schema} />);

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Reset columns" }))
      .not.toBeInTheDocument();
  });

  test("filters the list down to the columns matching the search", async () => {
    // GIVEN
    const component = await render(<ColumnsEditor schema={objectSchema} />);

    // WHEN
    await component.getByRole("searchbox").fill("note");

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Internal note" })).toBeVisible();
    await expect
      .element(component.getByRole("menuitem", { name: "Description" }))
      .not.toBeInTheDocument();
  });

  test("tells the user when no column matches the search", async () => {
    // GIVEN
    const component = await render(<ColumnsEditor schema={objectSchema} />);

    // WHEN
    await component.getByRole("searchbox").fill("nothing matches this");

    // THEN
    await expect.element(component.getByText("No fields match")).toBeVisible();
  });

  test("never offers the identity column", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({ name: "id", label: "Identifier", kind: "Text" }),
        generateAttributeSchema({ name: "name", label: "Name", kind: "Text" }),
      ],
      relationships: [],
    });

    // WHEN
    const component = await render(<ColumnsEditor schema={schema} />);

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Name" })).toBeVisible();
    await expect
      .element(component.getByRole("menuitem", { name: "Identifier" }))
      .not.toBeInTheDocument();
  });

  test("ignores a column the param names but the schema does not have", async () => {
    // GIVEN
    seedColumnsInUrl({ hidden: "not_a_field,description" });

    // WHEN
    const component = await render(<ColumnsEditor schema={objectSchema} />);

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "Description" }).getByText("visible"))
      .not.toBeInTheDocument();
    await expect
      .element(component.getByRole("menuitem", { name: "Name" }).getByText("visible"))
      .toBeInTheDocument();
  });

  test("marks the column carrying the active sort", async () => {
    // GIVEN
    seedParamInUrl("sort", "description__value__desc");

    // WHEN
    const component = await render(<ColumnsEditor schema={objectSchema} />);

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "Description" }).getByText("active sort"))
      .toBeInTheDocument();
    await expect
      .element(component.getByRole("menuitem", { name: "Name" }).getByText("active sort"))
      .not.toBeInTheDocument();
  });

  test("keeps the column carrying the active sort selectable", async () => {
    // GIVEN
    seedParamInUrl("sort", "description__value__desc");
    const component = await render(<ColumnsEditor schema={objectSchema} />);

    // WHEN
    await component.getByRole("menuitem", { name: "Description" }).click();

    // THEN
    await expect.poll(getHiddenColumnsInUrl).toBe("description");
  });

  test("marks the column carrying an active filter", async () => {
    // GIVEN
    seedParamInUrl("filters", '[{"name":"description__value","value":"core"}]');

    // WHEN
    const component = await render(<ColumnsEditor schema={objectSchema} />);

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "Description" }).getByText("active filter"))
      .toBeInTheDocument();
    await expect
      .element(component.getByRole("menuitem", { name: "Name" }).getByText("active filter"))
      .not.toBeInTheDocument();
  });

  test("leaves a column both params name hidden", async () => {
    // GIVEN
    seedColumnsInUrl({ hidden: "internal_note", shown: "internal_note" });

    // WHEN
    const component = await render(<ColumnsEditor schema={objectSchema} />);

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "Internal note" }).getByText("visible"))
      .not.toBeInTheDocument();
  });

  test("offers only the default columns on a surface that cannot reveal", async () => {
    // GIVEN
    const schema = objectSchema;

    // WHEN
    const component = await render(
      <ColumnsEditor schema={schema} surface={RELATIONSHIP_COLUMN_SURFACE} />
    );

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Description" })).toBeVisible();
    await expect
      .element(component.getByRole("menuitem", { name: "Internal note" }))
      .not.toBeInTheDocument();
  });
});
