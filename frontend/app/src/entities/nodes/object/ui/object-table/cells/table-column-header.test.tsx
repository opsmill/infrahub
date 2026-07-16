import { beforeEach, describe, expect, test } from "vitest";

import { render } from "../../../../../../../tests/components/render";
import {
  generateAttributeSchema,
  generateNodeSchema,
} from "../../../../../../../tests/fake/schema";
import { TableColumnHeader } from "./table-column-header";

const nameAttribute = generateAttributeSchema({ name: "name", label: "Name", kind: "Text" });
const jsonAttribute = generateAttributeSchema({ name: "config", label: "Config", kind: "JSON" });

const schema = generateNodeSchema({
  order_by: ["name__value"],
  attributes: [
    nameAttribute,
    generateAttributeSchema({ name: "description", label: "Description", kind: "Text" }),
    jsonAttribute,
  ],
  relationships: [],
});

const seedSortInUrl = (sort: string) =>
  window.history.replaceState(null, "", `${window.location.pathname}?sort=${sort}`);

const seedFiltersInUrl = (filters: Array<{ name: string; value: unknown }>) =>
  window.history.replaceState(
    null,
    "",
    `${window.location.pathname}?filters=${encodeURIComponent(JSON.stringify(filters))}`
  );

const getSortInUrl = () => new URLSearchParams(window.location.search).get("sort");

describe("TableColumnHeader", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", window.location.pathname);
  });

  test("offers both sort directions then a filter entry for a sortable attribute column", async () => {
    // GIVEN
    const component = await render(
      <TableColumnHeader schema={schema} columnSchema={nameAttribute} />
    );

    // WHEN
    await component.getByRole("button", { name: "Name" }).click();

    // THEN
    await expect
      .element(component.getByRole("menuitemradio", { name: "Sort ascending" }))
      .toBeVisible();
    await expect
      .element(component.getByRole("menuitemradio", { name: "Sort descending" }))
      .toBeVisible();
    await expect.element(component.getByRole("menuitem", { name: "Filter…" })).toBeVisible();
    const itemLabels = Array.from(
      document.querySelectorAll(
        '[role="menu"] [role="menuitemradio"], [role="menu"] [role="menuitem"]'
      )
    ).map((item) => item.textContent);
    expect(itemLabels).toEqual(["Sort ascending", "Sort descending", "Filter…"]);
  });

  test("replaces the whole custom sort with a single-field sort", async () => {
    // GIVEN
    seedSortInUrl("description__value__asc,name__value__desc");
    const component = await render(
      <TableColumnHeader schema={schema} columnSchema={nameAttribute} />
    );

    // WHEN
    await component.getByRole("button", { name: "Name" }).click();
    await component.getByRole("menuitemradio", { name: "Sort ascending" }).click();

    // THEN
    await expect.poll(getSortInUrl).toBe("name__value__asc");
  });

  test("toggle-clears the sort when selecting the active direction again", async () => {
    // GIVEN
    seedSortInUrl("name__value__desc");
    const component = await render(
      <TableColumnHeader schema={schema} columnSchema={nameAttribute} />
    );

    // WHEN
    await component.getByRole("button", { name: "Name" }).click();
    await component.getByRole("menuitemradio", { name: "Sort descending" }).click();

    // THEN
    await expect.poll(getSortInUrl).toBeNull();
  });

  test("marks the active direction as selected in the menu", async () => {
    // GIVEN
    seedSortInUrl("name__value__desc");
    const component = await render(
      <TableColumnHeader schema={schema} columnSchema={nameAttribute} />
    );

    // WHEN
    await component.getByRole("button", { name: "Name" }).click();

    // THEN
    await expect
      .element(component.getByRole("menuitemradio", { name: "Sort descending" }))
      .toHaveAttribute("aria-checked", "true");
    await expect
      .element(component.getByRole("menuitemradio", { name: "Sort ascending" }))
      .toHaveAttribute("aria-checked", "false");
  });

  test("shows a direction indicator on the header for a custom sort", async () => {
    // GIVEN
    seedSortInUrl("name__value__desc");

    // WHEN
    const component = await render(
      <TableColumnHeader schema={schema} columnSchema={nameAttribute} />
    );

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Name sorted descending" }))
      .toBeVisible();
  });

  test("shows no direction indicator for the schema default order", async () => {
    // GIVEN
    const component = await render(
      <TableColumnHeader schema={schema} columnSchema={nameAttribute} />
    );

    // THEN
    await expect.element(component.getByRole("button", { name: "Name" })).toBeVisible();
    await expect.element(component.getByRole("button", { name: "sorted" })).not.toBeInTheDocument();
  });

  test("offers only the filter entry for a non-sortable attribute kind", async () => {
    // GIVEN
    const component = await render(
      <TableColumnHeader schema={schema} columnSchema={jsonAttribute} />
    );

    // WHEN
    await component.getByRole("button", { name: "Config" }).click();

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Filter…" })).toBeVisible();
    await expect
      .element(component.getByRole("menuitemradio", { name: "Sort ascending" }))
      .not.toBeInTheDocument();
    await expect
      .element(component.getByRole("menuitemradio", { name: "Sort descending" }))
      .not.toBeInTheDocument();
  });

  test("opens the filter form pre-filled when a filter is active on the column", async () => {
    // GIVEN
    seedFiltersInUrl([{ name: "name__value", value: "atl" }]);
    const component = await render(
      <TableColumnHeader schema={schema} columnSchema={nameAttribute} />
    );

    // WHEN
    await component.getByRole("button", { name: "Name" }).click();
    await component.getByRole("menuitem", { name: "Filter…" }).click();

    // THEN
    await expect.element(component.getByRole("textbox")).toHaveValue("atl");
  });

  test("writes the same filter state as the toolbar filter path", async () => {
    // GIVEN
    const component = await render(
      <TableColumnHeader schema={schema} columnSchema={nameAttribute} />
    );

    // WHEN
    await component.getByRole("button", { name: "Name" }).click();
    await component.getByRole("menuitem", { name: "Filter…" }).click();
    await component.getByRole("textbox").fill("atl");
    await component.getByRole("button", { name: "Apply" }).click();

    // THEN
    await expect
      .poll(() => new URLSearchParams(window.location.search).get("filters"))
      .toBe(JSON.stringify([{ name: "name__value", value: "atl" }]));
  });
});
