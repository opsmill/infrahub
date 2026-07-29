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
    const items = component.getByRole("menuitemradio");

    // THEN
    await expect.element(items.nth(0)).toHaveTextContent("Newest");
    await expect.element(items.nth(1)).toHaveTextContent("Oldest");
    await expect.element(items.nth(2)).toHaveTextContent("Recently updated");
    await expect.element(items.nth(3)).toHaveTextContent("Least recently updated");
  });

  test("checks the default order when no sort is in the URL", async () => {
    // GIVEN
    const component = await renderSortMenu();

    // WHEN
    const newest = component.getByRole("menuitemradio", { name: "Newest", exact: true });

    // THEN
    await expect.element(newest).toHaveAttribute("aria-checked", "true");
  });

  test("checks the order carried by the URL", async () => {
    // GIVEN
    const component = await renderSortMenu({
      searchParams: "?sort=node_metadata__updated_at__desc",
    });

    // WHEN
    const recentlyUpdated = component.getByRole("menuitemradio", {
      name: "Recently updated",
      exact: true,
    });

    // THEN
    await expect.element(recentlyUpdated).toHaveAttribute("aria-checked", "true");
  });

  test("checks nothing for a sort the menu does not offer", async () => {
    // GIVEN
    const component = await renderSortMenu({ searchParams: "?sort=name__value__asc" });

    // WHEN
    const items = component.getByRole("menuitemradio");

    // THEN
    await expect.element(items.nth(0)).toHaveAttribute("aria-checked", "false");
    await expect.element(items.nth(2)).toHaveAttribute("aria-checked", "false");
  });

  test("writes the selected order to the URL", async () => {
    // GIVEN
    const onUrlUpdate = vi.fn<OnUrlUpdateFunction>();
    const component = await renderSortMenu({ onUrlUpdate });

    // WHEN
    await component.getByRole("menuitemradio", { name: "Least recently updated" }).click();

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
    await component.getByRole("menuitemradio", { name: "Newest", exact: true }).click();

    // THEN
    expect(onUrlUpdate.mock.lastCall?.[0]?.searchParams.get("sort")).toBeNull();
  });
});
