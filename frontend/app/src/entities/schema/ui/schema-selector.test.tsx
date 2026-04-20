import { beforeEach, describe, expect, test } from "vitest";

import { store } from "@/shared/stores";

import {
  genericSchemasAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
  templateSchemasAtom,
} from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../tests/components/render";
import { generateNodeSchema } from "../../../../tests/fake/schema";
import { SchemaSelector } from "./schema-selector";

describe("SchemaSelector Component", () => {
  const builtinTag = generateNodeSchema({
    kind: "BuiltinTag",
    name: "TagItem",
    namespace: "Builtin",
    label: "TagItem",
    description: "builtin-description",
  });
  const coreAccount = generateNodeSchema({
    kind: "CoreAccount",
    name: "AccountItem",
    namespace: "Core",
    label: "AccountItem",
    description: "core-description",
  });

  beforeEach(() => {
    store.set(nodeSchemasAtom, [builtinTag, coreAccount]);
    store.set(genericSchemasAtom, []);
    store.set(profileSchemasAtom, []);
    store.set(templateSchemasAtom, []);
  });

  test("renders namespaces expanded by default", async () => {
    // GIVEN
    const component = await render(<SchemaSelector />);

    // THEN
    await expect.element(component.getByText("TagItem")).toBeVisible();
    await expect.element(component.getByText("AccountItem")).toBeVisible();
  });

  test("collapses all namespaces when clicking the collapse button", async () => {
    // GIVEN
    const component = await render(<SchemaSelector />);

    // WHEN
    await component.getByRole("button", { name: "Collapse all" }).click();

    // THEN
    await expect.element(component.getByText("TagItem")).not.toBeInTheDocument();
    await expect.element(component.getByText("AccountItem")).not.toBeInTheDocument();
  });

  test("expands all namespaces when clicking the expand button after collapsing", async () => {
    // GIVEN
    const component = await render(<SchemaSelector />);
    await component.getByRole("button", { name: "Collapse all" }).click();

    // WHEN
    await component.getByRole("button", { name: "Expand all" }).click();

    // THEN
    await expect.element(component.getByText("TagItem")).toBeVisible();
    await expect.element(component.getByText("AccountItem")).toBeVisible();
  });

  test("collapse button hides all open sections even if only some are open", async () => {
    // GIVEN
    const component = await render(<SchemaSelector />);
    await component.getByText("Builtin").first().click();

    // WHEN
    await component.getByRole("button", { name: "Collapse all" }).click();

    // THEN
    await expect.element(component.getByText("TagItem")).not.toBeInTheDocument();
    await expect.element(component.getByText("AccountItem")).not.toBeInTheDocument();
  });

  test("auto-expands sections containing a search match", async () => {
    // GIVEN
    const component = await render(<SchemaSelector />);
    await component.getByRole("button", { name: "Collapse all" }).click();

    // WHEN
    await component.getByPlaceholder("Search schema").fill("account");

    // THEN
    await expect.element(component.getByText("AccountItem")).toBeVisible();
  });

  test("restores pre-search state when the search is cleared", async () => {
    // GIVEN
    const component = await render(<SchemaSelector />);
    await component.getByRole("button", { name: "Collapse all" }).click();

    // WHEN
    const searchInput = component.getByPlaceholder("Search schema");
    await searchInput.fill("account");
    await expect.element(component.getByText("AccountItem")).toBeVisible();
    await searchInput.fill("");

    // THEN
    await expect.element(component.getByText("AccountItem")).not.toBeInTheDocument();
    await expect.element(component.getByText("TagItem")).not.toBeInTheDocument();
  });

  test("preserves collapse-all action from within search after the search is cleared", async () => {
    // GIVEN
    const component = await render(<SchemaSelector />);
    const searchInput = component.getByPlaceholder("Search schema");
    await searchInput.fill("account");
    await expect.element(component.getByText("AccountItem")).toBeVisible();

    // WHEN
    await component.getByRole("button", { name: "Collapse all" }).click();
    await searchInput.fill("");

    // THEN
    await expect.element(component.getByText("AccountItem")).not.toBeInTheDocument();
    await expect.element(component.getByText("TagItem")).not.toBeInTheDocument();
  });

  test("allows collapsing matching sections while searching", async () => {
    // GIVEN
    const component = await render(<SchemaSelector />);
    await component.getByPlaceholder("Search schema").fill("account");
    await expect.element(component.getByText("AccountItem")).toBeVisible();

    // WHEN
    await component.getByRole("button", { name: "Collapse all" }).click();

    // THEN
    await expect.element(component.getByText("AccountItem")).not.toBeInTheDocument();
  });
});
