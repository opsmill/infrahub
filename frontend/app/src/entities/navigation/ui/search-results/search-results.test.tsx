import { afterEach, describe, expect, test, vi } from "vitest";
import { userEvent } from "vitest/browser";
import { cleanup } from "vitest-browser-react";

import type {
  ObjectResult,
  SearchAnywhereResult,
} from "@/entities/navigation/domain/use-cases/search-anywhere";
import { useGetSearchResultsPage } from "@/entities/navigation/ui/queries/search-anywhere.query";
import { useGetSearchResultObject } from "@/entities/navigation/ui/search-anywhere/search-result-node";

import { render } from "../../../../../tests/components/render";
import { generateNodeSchema } from "../../../../../tests/fake/schema";
import { SearchResults } from "./search-results";

vi.mock("@/entities/navigation/ui/queries/search-anywhere.query", async (importOriginal) => ({
  ...(await importOriginal()),
  useGetSearchResultsPage: vi.fn(),
}));

vi.mock("@/entities/navigation/ui/search-anywhere/search-result-node", async (importOriginal) => ({
  ...(await importOriginal()),
  useGetSearchResultObject: vi.fn(),
}));

const initialUrl = `${window.location.pathname}${window.location.search}`;

const tag = (index: number): ObjectResult => ({ id: `tag-${index}`, kind: "BuiltinTag" });

const tags = (count: number) => Array.from({ length: count }, (_, index) => tag(index + 1));

const respondWith = (
  result: Partial<SearchAnywhereResult>,
  { isPlaceholderData = false }: { isPlaceholderData?: boolean } = {}
) => {
  vi.mocked(useGetSearchResultsPage).mockReturnValue({
    data: { matchingObjects: [], hasMore: false, parentPrefixes: null, ...result },
    error: null,
    isPending: false,
    isPlaceholderData,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useGetSearchResultsPage>);
};

const renderAt = (url: string, { failingIds = [] }: { failingIds?: string[] } = {}) => {
  window.history.replaceState(null, "", url);
  vi.mocked(useGetSearchResultObject).mockImplementation((node) =>
    failingIds.includes(node.id)
      ? {
          schema: generateNodeSchema({ kind: node.kind }),
          object: undefined,
          isPending: false,
          error: new Error(`Cannot find Tag with id ${node.id}`),
        }
      : {
          schema: generateNodeSchema({ kind: node.kind }),
          object: { id: node.id, __typename: node.kind },
          isPending: false,
          error: null,
        }
  );

  return render(<SearchResults />);
};

describe("SearchResults", () => {
  afterEach(async () => {
    await cleanup();
    vi.resetAllMocks();
    window.history.replaceState(null, "", initialUrl);
  });

  test("links each matching object to its details page", async () => {
    // GIVEN
    respondWith({ matchingObjects: [tag(1)] });

    // WHEN
    const component = await renderAt("/search?q=atl");

    // THEN
    await expect
      .element(component.getByRole("link", { name: /^tag-1 / }))
      .toHaveAttribute("href", "/objects/BuiltinTag/tag-1");
    expect(useGetSearchResultsPage).toHaveBeenCalledWith({
      search: "atl",
      caseSensitive: false,
      page: 1,
    });
  });

  test("lists the next results when the user goes to the next page", async () => {
    // GIVEN
    respondWith({ matchingObjects: tags(20), hasMore: true });
    const component = await renderAt("/search?q=atl");

    // WHEN
    await component.getByRole("button", { name: "Next" }).click();

    // THEN
    await expect.poll(() => window.location.search).toBe("?q=atl&page=2");
    expect(useGetSearchResultsPage).toHaveBeenLastCalledWith({
      search: "atl",
      caseSensitive: false,
      page: 2,
    });
  });

  test("names the rows listed on a later page", async () => {
    // GIVEN
    respondWith({ matchingObjects: tags(20), hasMore: false });

    // WHEN
    const component = await renderAt("/search?q=atl&page=2");

    // THEN
    await expect.element(component.getByText("Showing results 21 to 40")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  test("disables the pager while the next page loads", async () => {
    // GIVEN
    respondWith({ matchingObjects: tags(20), hasMore: true }, { isPlaceholderData: true });

    // WHEN
    const component = await renderAt("/search?q=atl&page=2");

    // THEN
    await expect.element(component.getByText("Loading page 2…")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Previous" })).toBeDisabled();
    await expect.element(component.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  test("keeps the pager while the first page loads after a later page", async () => {
    // GIVEN
    respondWith({ matchingObjects: tags(5), hasMore: false }, { isPlaceholderData: true });

    // WHEN
    const component = await renderAt("/search?q=atl");

    // THEN
    await expect.element(component.getByText("Loading page 1…")).toBeVisible();
  });

  test("says which matching object could not be loaded", async () => {
    // GIVEN
    respondWith({ matchingObjects: [tag(1), tag(2)] });

    // WHEN
    const component = await renderAt("/search?q=atl", { failingIds: ["tag-2"] });

    // THEN
    await expect.element(component.getByText("Could not load Tag tag-2.")).toBeVisible();
    await expect.element(component.getByRole("link", { name: /^tag-1 / })).toBeVisible();
  });

  test("lists the parent prefixes on the first page only", async () => {
    // GIVEN
    respondWith({
      matchingObjects: tags(1),
      parentPrefixes: [{ id: "prefix-1", kind: "IpamIPPrefix" }],
    });

    // WHEN
    const component = await renderAt("/search?q=10.0.0.1&page=2");

    // THEN
    await expect.element(component.getByRole("region", { name: "Objects" })).toBeVisible();
    await expect
      .element(component.getByRole("region", { name: "Parent prefixes" }))
      .not.toBeInTheDocument();
  });

  test("treats a search of only spaces as no search text", async () => {
    // GIVEN
    respondWith({});

    // WHEN
    const component = await renderAt("/search?q=%20%20");

    // THEN
    await expect.element(component.getByText("No search text")).toBeVisible();
    expect(useGetSearchResultsPage).toHaveBeenCalledWith({
      search: "",
      caseSensitive: false,
      page: 1,
    });
  });

  test("starts again from the first page when the user searches for another text", async () => {
    // GIVEN
    respondWith({ matchingObjects: [tag(1)] });
    const component = await renderAt("/search?q=atl&page=3");

    // WHEN
    await component.getByRole("searchbox", { name: "Search text" }).fill("  dc1  ");
    await userEvent.keyboard("{enter}");

    // THEN
    await expect.poll(() => window.location.search).toBe("?q=dc1");
  });

  test("starts again from the first page when the user turns on case-sensitive search", async () => {
    // GIVEN
    respondWith({ matchingObjects: [tag(1)] });
    const component = await renderAt("/search?q=atl&page=2");

    // WHEN
    await component.getByRole("button", { name: "Case sensitive" }).click();

    // THEN
    await expect.poll(() => window.location.search).toBe("?q=atl&case_sensitive=true");
  });

  test("lists the prefixes that contain a searched IP address", async () => {
    // GIVEN
    respondWith({ parentPrefixes: [{ id: "prefix-1", kind: "IpamIPPrefix" }] });

    // WHEN
    const component = await renderAt("/search?q=10.0.0.1");

    // THEN
    await expect
      .element(
        component
          .getByRole("region", { name: "Parent prefixes" })
          .getByRole("link", { name: /^prefix-1 / })
      )
      .toHaveAttribute("href", "/objects/IpamIPPrefix/prefix-1");
  });

  test("says that no object matches the search", async () => {
    // GIVEN
    respondWith({ matchingObjects: [] });

    // WHEN
    const component = await renderAt("/search?q=zzz");

    // THEN
    await expect.element(component.getByText('No objects match "zzz".')).toBeVisible();
  });

  test("offers the first page when the page in the URL lists no results", async () => {
    // GIVEN
    respondWith({ matchingObjects: [] });

    // WHEN
    const component = await renderAt("/search?q=atl&page=5");

    // THEN
    await expect.element(component.getByText("Page 5 has no results.")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Go to first page" })).toBeVisible();
  });

  test("asks for a search text when the URL has none", async () => {
    // GIVEN
    respondWith({});

    // WHEN
    const component = await renderAt("/search");

    // THEN
    await expect.element(component.getByText("No search text")).toBeVisible();
  });
});
