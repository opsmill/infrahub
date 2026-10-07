import { beforeEach, describe, expect, test } from "vitest";

import { QSP } from "@/shared/config/qsp";

import { SEARCH_ANY_FILTER } from "@/entities/nodes/filters/domain/model/filter";

import { render } from "../../../../../../tests/components/render";
import { FilterSearchInput } from "./filter-search-input";

const seedSearchInUrl = (search: string) =>
  window.history.replaceState(
    null,
    "",
    `${window.location.pathname}?${QSP.FILTER}=${encodeURIComponent(
      JSON.stringify([{ name: SEARCH_ANY_FILTER, value: search }])
    )}`
  );

const getSearchInUrl = (): string | undefined => {
  const filters = new URLSearchParams(window.location.search).get(QSP.FILTER);
  if (!filters) return;

  return JSON.parse(filters).find(
    (filter: { name: string; value: string }) => filter.name === SEARCH_ANY_FILTER
  )?.value;
};

describe("FilterSearchInput", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", window.location.pathname);
  });

  test("searches for pasted text without its surrounding whitespace", async () => {
    const component = await render(<FilterSearchInput />);

    await component.getByRole("searchbox").fill("  spine1 ");

    await expect.poll(getSearchInUrl).toBe("spine1");
  });

  test("keeps a typed trailing space in the input once the search runs", async () => {
    const component = await render(<FilterSearchInput />);
    const input = component.getByRole("searchbox");

    await input.fill("core ");

    await expect.poll(getSearchInUrl).toBe("core");
    await expect.element(input).toHaveValue("core ");
  });

  test("removes the search when the input holds only whitespace", async () => {
    seedSearchInUrl("spine1");
    const component = await render(<FilterSearchInput />);

    await component.getByRole("searchbox").fill("   ");

    await expect.poll(getSearchInUrl).toBeUndefined();
  });
});
