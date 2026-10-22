import { Command } from "cmdk";
import { afterEach, describe, expect, test } from "vitest";

import { store } from "@/shared/stores";

import { searchExactMatchAtom } from "@/entities/navigation/stores/search-exact-match.atom";
import { SearchAnywhereInput } from "@/entities/navigation/ui/search-anywhere/search-anywhere-input";

import { render } from "../../../../../tests/components/render";

describe("SearchAnywhereInput", () => {
  afterEach(() => {
    store.set(searchExactMatchAtom, false);
  });

  test("presses the exact match toggle when it is clicked", async () => {
    // GIVEN
    const component = await render(
      <Command>
        <SearchAnywhereInput />
      </Command>
    );

    // WHEN
    await component.getByRole("button", { name: "Exact match" }).click();

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Exact match" }))
      .toHaveAttribute("aria-pressed", "true");
    expect(store.get(searchExactMatchAtom)).toBe(true);
  });
});
