import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { QSP } from "@/shared/config/qsp";
import { store } from "@/shared/stores";

import type { Filter } from "@/entities/nodes/filters/domain/model/filter";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../tests/components/render";
import { generateNodeSchema } from "../../../../../tests/fake/schema";
import { GlobalEventsFilters } from "./global-events-filters";

const blueTag = { id: "tag-1", __typename: "BuiltinTag", display_label: "blue" };

function seedFilters(filters: Filter[]) {
  window.history.replaceState(
    null,
    "",
    `/?${QSP.FILTER}=${encodeURIComponent(JSON.stringify(filters))}`
  );
}

function getAppliedFilters(): Filter[] {
  const raw = new URLSearchParams(window.location.search).get(QSP.FILTER);

  return raw ? JSON.parse(raw) : [];
}

describe("GlobalEventsFilters", () => {
  const initialNodeSchemas = store.get(nodeSchemasAtom);

  beforeAll(() => {
    store.set(nodeSchemasAtom, [
      generateNodeSchema({ kind: "BuiltinTag", display_labels: ["name__value"] }),
    ]);
  });

  afterAll(() => {
    store.set(nodeSchemasAtom, initialNodeSchemas);
  });

  afterEach(() => {
    window.history.replaceState(null, "", window.location.pathname);
  });

  it("removes only the event type filter when its value is clicked", async () => {
    // GIVEN
    seedFilters([
      { name: "branches__value", value: "main" },
      { name: "eventType__value", value: "infrahub.node.created" },
      { name: "hasChildren__value", value: true },
    ]);
    const component = await render(<GlobalEventsFilters />);

    // WHEN
    await component.getByText("Node created", { exact: true }).click();

    // THEN
    await expect.poll(getAppliedFilters).toEqual([
      { name: "branches__value", value: "main" },
      { name: "hasChildren__value", value: true },
    ]);
  });

  it("removes only the primary node filter when its value is clicked", async () => {
    // GIVEN
    seedFilters([
      { name: "branches__value", value: "main" },
      { name: "primaryNodeIds__value", value: [blueTag] },
      { name: "relatedNodeIds__value", value: [blueTag] },
    ]);
    const component = await render(<GlobalEventsFilters />);

    // WHEN
    await component
      .getByRole("button", { name: "Primary Node blue", exact: true })
      .getByText("blue", { exact: true })
      .click();

    // THEN
    await expect.poll(getAppliedFilters).toEqual([
      { name: "branches__value", value: "main" },
      { name: "relatedNodeIds__value", value: [blueTag] },
    ]);
  });

  it("keeps a null branch filter when the branch value is clicked", async () => {
    // GIVEN
    seedFilters([{ name: "branches__value", value: "main" }]);
    const component = await render(<GlobalEventsFilters />);

    // WHEN
    await component.getByText("main", { exact: true }).click();

    // THEN
    await expect.poll(getAppliedFilters).toEqual([{ name: "branches__value", value: null }]);
  });

  it("shows the branch tag with its own accessible name and value", async () => {
    // GIVEN
    seedFilters([{ name: "branches__value", value: "main" }]);

    // WHEN
    const component = await render(<GlobalEventsFilters />);

    // THEN
    await expect
      .element(component.getByRole("row", { name: "branches contains main" }))
      .toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Branch main", exact: true }))
      .toBeVisible();
  });

  it("names the branch form 'Filter by branch'", async () => {
    // GIVEN
    seedFilters([{ name: "branches__value", value: null }]);
    const component = await render(<GlobalEventsFilters />);

    // WHEN
    await component.getByRole("button", { name: "Branch", exact: true }).click();

    // THEN
    await expect
      .element(component.getByRole("dialog").getByText("branch", { exact: true }))
      .toBeVisible();
  });

  it("shows a false Has Children value", async () => {
    // GIVEN
    seedFilters([
      { name: "branches__value", value: "main" },
      { name: "hasChildren__value", value: false },
    ]);

    // WHEN
    const component = await render(<GlobalEventsFilters />);

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Has Children false", exact: true }))
      .toBeVisible();
  });

  it("shows the node labels of a primary node filter", async () => {
    // GIVEN
    seedFilters([
      { name: "branches__value", value: "main" },
      { name: "primaryNodeIds__value", value: [blueTag] },
    ]);

    // WHEN
    const component = await render(<GlobalEventsFilters />);

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Primary Node blue", exact: true }))
      .toBeVisible();
  });

  it("shows a primary node filter without a value as empty", async () => {
    // GIVEN
    seedFilters([
      { name: "branches__value", value: "main" },
      { name: "primaryNodeIds__value", value: null },
    ]);

    // WHEN
    const component = await render(<GlobalEventsFilters />);

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Primary Node", exact: true }))
      .toBeVisible();
  });

  it("applies a Has Children value and closes the form", async () => {
    // GIVEN
    seedFilters([{ name: "branches__value", value: "main" }]);
    const component = await render(<GlobalEventsFilters />);
    await component.getByRole("button", { name: "Has Children", exact: true }).click();
    await component.getByText("True", { exact: true }).click();

    // WHEN
    await component.getByRole("button", { name: "Apply" }).click();

    // THEN
    await expect.poll(getAppliedFilters).toEqual([
      { name: "branches__value", value: "main" },
      { name: "hasChildren__value", value: true },
    ]);
    await expect.element(component.getByRole("dialog")).not.toBeInTheDocument();
  });
});
