import { beforeEach, describe, expect, test } from "vitest";

import { store } from "@/shared/stores";

import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../../tests/components/render";
import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../../tests/fake/schema";
import { TableColumnHeader } from "./table-column-header";

const nameAttribute = generateAttributeSchema({ name: "name", label: "Name", kind: "Text" });
const jsonAttribute = generateAttributeSchema({ name: "config", label: "Config", kind: "JSON" });

const siteRelationship = generateRelationshipSchema({
  name: "site",
  label: "Site",
  peer: "LocationSite",
  cardinality: "one",
});
const tagsRelationship = generateRelationshipSchema({
  name: "tags",
  label: "Tags",
  peer: "LocationSite",
  cardinality: "many",
});
const ownerRelationship = generateRelationshipSchema({
  name: "owner",
  label: "Owner",
  peer: "UnknownKind",
  cardinality: "one",
});

const siteSchema = generateNodeSchema({
  kind: "LocationSite",
  attributes: [
    generateAttributeSchema({ name: "name", label: "Name", kind: "Text", order_weight: 1000 }),
    generateAttributeSchema({
      name: "description",
      label: "Description",
      kind: "Text",
      order_weight: 2000,
    }),
    generateAttributeSchema({
      name: "metadata",
      label: "Metadata",
      kind: "JSON",
      order_weight: 3000,
    }),
  ],
  relationships: [],
});

const schema = generateNodeSchema({
  order_by: ["name__value"],
  attributes: [
    nameAttribute,
    generateAttributeSchema({ name: "description", label: "Description", kind: "Text" }),
    jsonAttribute,
  ],
  relationships: [siteRelationship, tagsRelationship, ownerRelationship],
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
    store.set(nodeSchemasAtom, [siteSchema]);
  });

  test("offers both sort directions then a filter entry for a sortable attribute column", async () => {
    // GIVEN
    const component = await render(
      <TableColumnHeader schema={schema} columnSchema={nameAttribute} />
    );

    // WHEN
    await component.getByRole("button", { name: "Name" }).click();

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Sort ascending" })).toBeVisible();
    await expect
      .element(component.getByRole("menuitem", { name: "Sort descending" }))
      .toBeVisible();
    await expect.element(component.getByRole("menuitem", { name: "Filter" })).toBeVisible();
    const itemLabels = Array.from(document.querySelectorAll('[role="menu"] [role="menuitem"]')).map(
      (item) => item.textContent
    );
    expect(itemLabels).toEqual(["Sort ascending", "Sort descending", "Filter"]);
  });

  test("replaces the whole custom sort with a single-field sort", async () => {
    // GIVEN
    seedSortInUrl("description__value__asc,name__value__desc");
    const component = await render(
      <TableColumnHeader schema={schema} columnSchema={nameAttribute} />
    );

    // WHEN
    await component.getByRole("button", { name: "Name" }).click();
    await component.getByRole("menuitem", { name: "Sort ascending" }).click();

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
    await component.getByRole("menuitem", { name: "Sort descending" }).click();

    // THEN
    await expect.poll(getSortInUrl).toBeNull();
  });

  test("marks the active direction in the menu", async () => {
    // GIVEN
    seedSortInUrl("name__value__desc");
    const component = await render(
      <TableColumnHeader schema={schema} columnSchema={nameAttribute} />
    );

    // WHEN
    await component.getByRole("button", { name: "Name" }).click();

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "Sort descending active" }))
      .toBeVisible();
    await expect
      .element(component.getByRole("menuitem", { name: "Sort ascending active" }))
      .not.toBeInTheDocument();
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
    await expect.element(component.getByRole("menuitem", { name: "Filter" })).toBeVisible();
    await expect
      .element(component.getByRole("menuitem", { name: "Sort ascending" }))
      .not.toBeInTheDocument();
    await expect
      .element(component.getByRole("menuitem", { name: "Sort descending" }))
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
    await component.getByRole("menuitem", { name: "Filter" }).click();

    // THEN
    await expect.element(component.getByRole("textbox")).toHaveValue("atl");
  });

  test("lists exactly the peer's sortable attributes in the Sort by submenu", async () => {
    // GIVEN
    const component = await render(
      <TableColumnHeader schema={schema} columnSchema={siteRelationship} />
    );

    // WHEN
    await component.getByRole("button", { name: "Site" }).click();
    await component.getByRole("menuitem", { name: "Sort by" }).click();

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Name" })).toBeVisible();
    const itemLabels = Array.from(
      document.querySelectorAll('[role="menu"][aria-label="Sort by Site"] [role="menuitem"]')
    ).map((item) => item.textContent);
    expect(itemLabels).toEqual(["Name", "Description"]);
  });

  test("writes the relationship sort field when selecting a peer attribute direction", async () => {
    // GIVEN
    const component = await render(
      <TableColumnHeader schema={schema} columnSchema={siteRelationship} />
    );

    // WHEN
    await component.getByRole("button", { name: "Site" }).click();
    await component.getByRole("menuitem", { name: "Sort by" }).click();
    await component.getByRole("menuitem", { name: "Name" }).click();
    await component.getByRole("menuitem", { name: "Ascending" }).click();

    // THEN
    await expect.poll(getSortInUrl).toBe("site__name__value__asc");
  });

  test("toggle-clears the sort when selecting the active peer attribute direction again", async () => {
    // GIVEN
    seedSortInUrl("site__name__value__asc");
    const component = await render(
      <TableColumnHeader schema={schema} columnSchema={siteRelationship} />
    );

    // WHEN
    await component.getByRole("button", { name: "Site" }).click();
    await component.getByRole("menuitem", { name: "Sort by" }).click();
    await component.getByRole("menuitem", { name: "Name" }).click();
    await component.getByRole("menuitem", { name: "Ascending" }).click();

    // THEN
    await expect.poll(getSortInUrl).toBeNull();
  });

  test("marks the active peer attribute and direction in the submenus", async () => {
    // GIVEN
    seedSortInUrl("site__name__value__desc");
    const component = await render(
      <TableColumnHeader schema={schema} columnSchema={siteRelationship} />
    );

    // WHEN
    await component.getByRole("button", { name: "Site" }).click();
    await component.getByRole("menuitem", { name: "Sort by" }).click();
    await component.getByRole("menuitem", { name: "Name active sort field" }).click();

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "Descending active" }))
      .toBeVisible();
    await expect
      .element(component.getByRole("menuitem", { name: "Ascending active" }))
      .not.toBeInTheDocument();
    await expect
      .element(component.getByRole("menuitem", { name: "Description active sort field" }))
      .not.toBeInTheDocument();
  });

  test("shows a direction indicator on the relationship header for an active relationship sort", async () => {
    // GIVEN
    seedSortInUrl("site__name__value__desc");

    // WHEN
    const component = await render(
      <TableColumnHeader schema={schema} columnSchema={siteRelationship} />
    );

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Site sorted descending" }))
      .toBeVisible();
  });

  test("offers only the filter entry for a cardinality-many relationship column", async () => {
    // GIVEN
    const component = await render(
      <TableColumnHeader schema={schema} columnSchema={tagsRelationship} />
    );

    // WHEN
    await component.getByRole("button", { name: "Tags" }).click();

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Filter" })).toBeVisible();
    await expect
      .element(component.getByRole("menuitem", { name: "Sort by" }))
      .not.toBeInTheDocument();
  });

  test("offers only the filter entry when the peer schema cannot be resolved", async () => {
    // GIVEN
    const component = await render(
      <TableColumnHeader schema={schema} columnSchema={ownerRelationship} />
    );

    // WHEN
    await component.getByRole("button", { name: "Owner" }).click();

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Filter" })).toBeVisible();
    await expect
      .element(component.getByRole("menuitem", { name: "Sort by" }))
      .not.toBeInTheDocument();
  });

  test("keeps the pagination offset unchanged when sorting from the header", async () => {
    // GIVEN
    const pagination = JSON.stringify({ limit: 10, offset: 20 });
    window.history.replaceState(
      null,
      "",
      `${window.location.pathname}?pagination=${encodeURIComponent(pagination)}`
    );
    const component = await render(
      <TableColumnHeader schema={schema} columnSchema={nameAttribute} />
    );

    // WHEN
    await component.getByRole("button", { name: "Name" }).click();
    await component.getByRole("menuitem", { name: "Sort ascending" }).click();

    // THEN
    await expect.poll(getSortInUrl).toBe("name__value__asc");
    expect(new URLSearchParams(window.location.search).get("pagination")).toBe(pagination);
  });

  test("renders a plain non-interactive header when isDisabled", async () => {
    // GIVEN
    const component = await render(
      <TableColumnHeader schema={schema} columnSchema={nameAttribute} isDisabled />
    );

    // THEN
    await expect.element(component.getByText("Name")).toBeVisible();
    await expect.element(component.getByRole("button")).not.toBeInTheDocument();
  });

  test("writes the same filter state as the toolbar filter path", async () => {
    // GIVEN
    const component = await render(
      <TableColumnHeader schema={schema} columnSchema={nameAttribute} />
    );

    // WHEN
    await component.getByRole("button", { name: "Name" }).click();
    await component.getByRole("menuitem", { name: "Filter" }).click();
    await component.getByRole("textbox").fill("atl");
    await component.getByRole("button", { name: "Apply" }).click();

    // THEN
    await expect
      .poll(() => new URLSearchParams(window.location.search).get("filters"))
      .toBe(JSON.stringify([{ name: "name__value", value: "atl" }]));
  });
});
