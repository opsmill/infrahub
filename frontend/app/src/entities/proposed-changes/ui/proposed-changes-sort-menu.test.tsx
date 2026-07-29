import { type OnUrlUpdateFunction, withNuqsTestingAdapter } from "nuqs/adapters/testing";
import { describe, expect, test, vi } from "vitest";
import { render } from "vitest-browser-react";

import { ProposedChangesSortMenu } from "@/entities/proposed-changes/ui/proposed-changes-sort-menu";

import { generateAttributeSchema, generateNodeSchema } from "../../../../tests/fake/schema";

const schema = generateNodeSchema({
  order_by: [],
  attributes: [generateAttributeSchema({ name: "name", label: "Name", kind: "Text" })],
  relationships: [],
});

// Menu items are addressed by position: an active item carries a visually hidden "active" label, so
// its accessible name no longer matches its own text exactly.
const OPTION = {
  newest: 0,
  oldest: 1,
  recentlyUpdated: 2,
  leastRecentlyUpdated: 3,
} as const;

const renderSortMenu = async ({
  searchParams = "",
  onUrlUpdate,
}: {
  searchParams?: string;
  onUrlUpdate?: OnUrlUpdateFunction;
} = {}) => {
  const component = await render(<ProposedChangesSortMenu schema={schema} />, {
    wrapper: withNuqsTestingAdapter({ searchParams, onUrlUpdate }),
  });

  await component.getByRole("button", { name: "Sort" }).click();

  return component;
};

describe("ProposedChangesSortMenu", () => {
  test("offers the four date orders", async () => {
    // GIVEN
    const component = await renderSortMenu();

    // WHEN
    const items = component.getByRole("menuitem");

    // THEN
    await expect.element(items.nth(OPTION.newest)).toHaveTextContent("Newest");
    await expect.element(items.nth(OPTION.oldest)).toHaveTextContent("Oldest");
    await expect.element(items.nth(OPTION.recentlyUpdated)).toHaveTextContent("Recently updated");
    await expect
      .element(items.nth(OPTION.leastRecentlyUpdated))
      .toHaveTextContent("Least recently updated");
  });

  test("marks the default order as active when no sort is in the URL", async () => {
    // GIVEN
    const component = await renderSortMenu();

    // WHEN
    const items = component.getByRole("menuitem");

    // THEN
    await expect.element(items.nth(OPTION.newest)).toHaveTextContent("active");
  });

  test("marks the order carried by the URL as active", async () => {
    // GIVEN
    const component = await renderSortMenu({
      searchParams: "?sort=node_metadata__updated_at__desc",
    });

    // WHEN
    const items = component.getByRole("menuitem");

    // THEN
    await expect.element(items.nth(OPTION.recentlyUpdated)).toHaveTextContent("active");
  });

  test("marks nothing as active for a sort the menu does not offer", async () => {
    // GIVEN
    const component = await renderSortMenu({ searchParams: "?sort=name__value__asc" });

    // WHEN
    const items = component.getByRole("menuitem");

    // THEN
    await expect.element(items.nth(OPTION.newest)).not.toHaveTextContent("active");
    await expect.element(items.nth(OPTION.recentlyUpdated)).not.toHaveTextContent("active");
  });

  test("writes the selected order to the URL", async () => {
    // GIVEN
    const onUrlUpdate = vi.fn<OnUrlUpdateFunction>();
    const component = await renderSortMenu({ onUrlUpdate });

    // WHEN
    await component.getByRole("menuitem").nth(OPTION.leastRecentlyUpdated).click();

    // THEN
    expect(onUrlUpdate.mock.lastCall?.[0]?.searchParams.get("sort")).toBe(
      "node_metadata__updated_at__asc"
    );
  });

  test("clears the query param when the default order is selected", async () => {
    // GIVEN
    const onUrlUpdate = vi.fn<OnUrlUpdateFunction>();
    const component = await renderSortMenu({
      searchParams: "?sort=node_metadata__updated_at__desc",
      onUrlUpdate,
    });

    // WHEN
    await component.getByRole("menuitem").nth(OPTION.newest).click();

    // THEN
    expect(onUrlUpdate.mock.lastCall?.[0]?.searchParams.get("sort")).toBeNull();
  });
});
