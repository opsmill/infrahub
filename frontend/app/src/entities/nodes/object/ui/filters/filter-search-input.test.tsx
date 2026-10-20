import { afterEach, describe, expect, test } from "vitest";

import { QSP } from "@/shared/config/qsp";

import { SEARCH_ANY_FILTER } from "@/entities/nodes/filters/domain/model/filter";

import { render } from "../../../../../../tests/components/render";
import { FilterResetButton } from "./filter-reset-button";
import { FilterSearchInput } from "./filter-search-input";

const seedSearchInUrl = (search: string) =>
  window.history.replaceState(
    null,
    "",
    `${window.location.pathname}?${QSP.FILTER}=${encodeURIComponent(
      JSON.stringify([{ name: SEARCH_ANY_FILTER, value: search }])
    )}`
  );

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const navigateToSearch = async (search: string) => {
  window.history.pushState(
    null,
    "",
    `${window.location.pathname}?${QSP.FILTER}=${encodeURIComponent(
      JSON.stringify([{ name: SEARCH_ANY_FILTER, value: search }])
    )}`
  );
  window.dispatchEvent(new PopStateEvent("popstate"));
  // Lets the component render the new URL, well within the input's 300 ms delay.
  await wait(50);
};

const getSearchInUrl = (): string | undefined => {
  const filters = new URLSearchParams(window.location.search).get(QSP.FILTER);
  if (!filters) return;

  return JSON.parse(filters).find(
    (filter: { name: string; value: string }) => filter.name === SEARCH_ANY_FILTER
  )?.value;
};

describe("FilterSearchInput", () => {
  afterEach(() => {
    window.history.replaceState(null, "", window.location.pathname);
  });

  test("searches for pasted text without its surrounding whitespace", async () => {
    // GIVEN
    const component = await render(<FilterSearchInput />);

    // WHEN
    await component.getByRole("searchbox").fill("  spine1 ");

    // THEN
    await expect.poll(getSearchInUrl).toBe("spine1");
  });

  test("keeps a typed trailing space in the input once the search runs", async () => {
    // GIVEN
    const component = await render(<FilterSearchInput />);
    const input = component.getByRole("searchbox");

    // WHEN
    await input.fill("core ");

    // THEN
    await expect.poll(getSearchInUrl).toBe("core");
    await expect.element(input).toHaveValue("core ");
  });

  test("removes the search when the input holds only whitespace", async () => {
    // GIVEN
    seedSearchInUrl("spine1");
    const component = await render(<FilterSearchInput />);

    // WHEN
    await component.getByRole("searchbox").fill("   ");

    // THEN
    await expect.poll(getSearchInUrl).toBeUndefined();
  });

  test("rewrites a search with surrounding whitespace in the URL without it", async () => {
    // GIVEN
    seedSearchInUrl("  spine1 ");

    // WHEN
    await render(<FilterSearchInput />);

    // THEN
    await expect.poll(getSearchInUrl).toBe("spine1");
  });

  test("rewrites a search with surrounding whitespace reached by browser navigation", async () => {
    // GIVEN
    seedSearchInUrl("spine1");
    await render(<FilterSearchInput />);

    // WHEN
    await navigateToSearch("  spine1 ");

    // THEN
    await expect.poll(getSearchInUrl).toBe("spine1");
  });

  test("stops on the search reached by a quick back then forward navigation", async () => {
    // GIVEN
    seedSearchInUrl("spine2");
    const component = await render(<FilterSearchInput />);

    // WHEN
    await navigateToSearch("spine1");
    await navigateToSearch("spine2");
    const historyLength = window.history.length;
    await wait(1000);

    // THEN
    expect(window.history.length).toBe(historyLength);
    expect(getSearchInUrl()).toBe("spine2");
    await expect.element(component.getByRole("searchbox")).toHaveValue("spine2");
  });

  test("empties the input when the filters are cleared", async () => {
    // GIVEN
    seedSearchInUrl("spine1");
    const component = await render(
      <>
        <FilterSearchInput />
        <FilterResetButton />
      </>
    );

    // WHEN
    await component.getByRole("button", { name: "Clear filters" }).click();

    // THEN
    await expect.element(component.getByRole("searchbox")).toHaveValue("");
  });
});
