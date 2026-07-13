import { beforeEach, describe, expect, test, vi } from "vitest";

import { store } from "@/shared/stores";

import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../tests/components/render";
import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../tests/fake/schema";
import { AddSortPicker } from "./add-sort-picker";

const site = generateNodeSchema({
  kind: "LocationSite",
  attributes: [
    generateAttributeSchema({ name: "name", label: "Name", kind: "Text", order_weight: 2000 }),
    generateAttributeSchema({
      name: "description",
      label: "Description",
      kind: "Text",
      order_weight: 1000,
    }),
    generateAttributeSchema({ name: "rack", label: null, kind: "Text", order_weight: 3000 }),
    generateAttributeSchema({ name: "metadata", kind: "JSON" }),
  ],
  relationships: [],
});

const vault = generateNodeSchema({
  kind: "SecretVault",
  attributes: [generateAttributeSchema({ name: "secret", kind: "Password" })],
  relationships: [],
});

const schema = generateNodeSchema({
  attributes: [generateAttributeSchema({ name: "name", label: "Name", kind: "Text" })],
  relationships: [
    generateRelationshipSchema({
      name: "site",
      label: "Site",
      peer: "LocationSite",
      cardinality: "one",
    }),
    generateRelationshipSchema({ name: "interfaces", peer: "LocationSite", cardinality: "many" }),
    generateRelationshipSchema({
      name: "vault",
      label: "Vault",
      peer: "SecretVault",
      cardinality: "one",
    }),
  ],
});

describe("AddSortPicker", () => {
  beforeEach(() => {
    store.set(nodeSchemasAtom, [site, vault]);
  });

  test("groups relationship fields under a submenu when search is empty", async () => {
    // GIVEN
    const component = await render(<AddSortPicker schema={schema} onSelect={vi.fn()} />);

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Name" })).toBeVisible();
    await expect.element(component.getByRole("menuitem", { name: "Site" })).toBeVisible();
    await expect.element(component.getByRole("menuitem", { name: "Created at" })).toBeVisible();
    await expect
      .element(component.getByRole("menuitem", { name: "Site › Description" }))
      .not.toBeInTheDocument();
    await expect
      .element(component.getByRole("menuitem", { name: "Description" }))
      .not.toBeInTheDocument();
    await expect
      .element(component.getByRole("menuitem", { name: "Vault" }))
      .not.toBeInTheDocument();
  });

  test("selects a relationship field with a direction through the submenu cascade", async () => {
    // GIVEN
    const onSelect = vi.fn();
    const component = await render(<AddSortPicker schema={schema} onSelect={onSelect} />);

    // WHEN
    await component.getByRole("menuitem", { name: "Site" }).click();
    await component.getByRole("menuitem", { name: "Description" }).click();
    await component.getByRole("menuitem", { name: "Ascending" }).click();

    // THEN
    expect(onSelect).toHaveBeenCalledWith({ field: "site__description__value", direction: "ASC" });
  });

  test("selects a node metadata field", async () => {
    // GIVEN
    const onSelect = vi.fn();
    const component = await render(<AddSortPicker schema={schema} onSelect={onSelect} />);

    // WHEN
    await component.getByRole("menuitem", { name: "Created at" }).click();
    await component.getByRole("menuitem", { name: "Ascending" }).click();

    // THEN
    expect(onSelect).toHaveBeenCalledWith({
      field: "node_metadata__created_at",
      direction: "ASC",
    });
  });

  test("selects the updated-at metadata field", async () => {
    // GIVEN
    const onSelect = vi.fn();
    const component = await render(<AddSortPicker schema={schema} onSelect={onSelect} />);

    // WHEN
    await component.getByRole("menuitem", { name: "Updated at" }).click();
    await component.getByRole("menuitem", { name: "Descending" }).click();

    // THEN
    expect(onSelect).toHaveBeenCalledWith({
      field: "node_metadata__updated_at",
      direction: "DESC",
    });
  });

  test("flattens fields with peer-prefixed labels when searching", async () => {
    // GIVEN
    const onSelect = vi.fn();
    const component = await render(<AddSortPicker schema={schema} onSelect={onSelect} />);

    // WHEN
    await component.getByRole("searchbox").fill("des");

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "Site › Description" }))
      .toBeVisible();
    await expect
      .element(component.getByRole("menuitem", { name: "Site", exact: true }))
      .not.toBeInTheDocument();

    // WHEN
    await component.getByRole("menuitem", { name: "Site › Description" }).click();
    await component.getByRole("menuitem", { name: "Descending" }).click();

    // THEN
    expect(onSelect).toHaveBeenCalledWith({
      field: "site__description__value",
      direction: "DESC",
    });
  });

  test("falls back to the attribute name in flat labels when the label is missing", async () => {
    // GIVEN
    const component = await render(<AddSortPicker schema={schema} onSelect={vi.fn()} />);

    // WHEN
    await component.getByRole("searchbox").fill("rack");

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Site › rack" })).toBeVisible();
  });

  test("hides an attribute that is already active", async () => {
    // GIVEN
    const component = await render(
      <AddSortPicker schema={schema} activeFields={new Set(["name__value"])} onSelect={vi.fn()} />
    );

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Site" })).toBeVisible();
    await expect.element(component.getByRole("menuitem", { name: "Name" })).not.toBeInTheDocument();
  });

  test("hides a metadata field that is already active", async () => {
    // GIVEN
    const component = await render(
      <AddSortPicker
        schema={schema}
        activeFields={new Set(["node_metadata__created_at"])}
        onSelect={vi.fn()}
      />
    );

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Updated at" })).toBeVisible();
    await expect
      .element(component.getByRole("menuitem", { name: "Created at" }))
      .not.toBeInTheDocument();
  });

  test("keeps a peer attribute visible when a same-named top-level attribute is active", async () => {
    // GIVEN
    const component = await render(
      <AddSortPicker schema={schema} activeFields={new Set(["name__value"])} onSelect={vi.fn()} />
    );

    // WHEN
    await component.getByRole("menuitem", { name: "Site" }).click();

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Name" })).toBeVisible();
  });

  test("hides only the peer attribute when a relationship field is active", async () => {
    // GIVEN
    const component = await render(
      <AddSortPicker
        schema={schema}
        activeFields={new Set(["site__name__value"])}
        onSelect={vi.fn()}
      />
    );

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Name" })).toBeVisible();

    // WHEN
    await component.getByRole("menuitem", { name: "Site" }).click();

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Description" })).toBeVisible();
    await expect
      .element(component.getByRole("menuitem", { name: "Name" }).nth(1))
      .not.toBeInTheDocument();
  });

  test("hides a relationship submenu when all its peer attributes are active", async () => {
    // GIVEN
    const component = await render(
      <AddSortPicker
        schema={schema}
        activeFields={
          new Set(["site__name__value", "site__description__value", "site__rack__value"])
        }
        onSelect={vi.fn()}
      />
    );

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Name" })).toBeVisible();
    await expect.element(component.getByRole("menuitem", { name: "Site" })).not.toBeInTheDocument();
  });

  test("hides active fields when searching", async () => {
    // GIVEN
    const component = await render(
      <AddSortPicker
        schema={schema}
        activeFields={new Set(["site__description__value"])}
        onSelect={vi.fn()}
      />
    );

    // WHEN
    await component.getByRole("searchbox").fill("des");

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "Site › Description" }))
      .not.toBeInTheDocument();
    await expect.element(component.getByText("No fields match")).toBeVisible();
  });

  test("shows an empty state when every field is already active", async () => {
    // GIVEN
    const standalone = generateNodeSchema({
      attributes: [generateAttributeSchema({ name: "name", label: "Name", kind: "Text" })],
      relationships: [],
    });
    const component = await render(
      <AddSortPicker
        schema={standalone}
        activeFields={
          new Set(["name__value", "node_metadata__created_at", "node_metadata__updated_at"])
        }
        onSelect={vi.fn()}
      />
    );

    // THEN
    await expect.element(component.getByText("All sortable fields are in use")).toBeVisible();
  });

  test("restores the grouped layout when the search is cleared", async () => {
    // GIVEN
    const component = await render(<AddSortPicker schema={schema} onSelect={vi.fn()} />);

    // WHEN
    await component.getByRole("searchbox").fill("des");
    await component.getByRole("searchbox").fill("");

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Site" })).toBeVisible();
    await expect
      .element(component.getByRole("menuitem", { name: "Site › Description" }))
      .not.toBeInTheDocument();
  });
});
