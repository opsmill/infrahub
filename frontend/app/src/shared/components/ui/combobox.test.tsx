import { describe, expect, it, onTestFinished, vi } from "vitest";
import { userEvent } from "vitest/browser";

import { ComboboxItem, ComboboxList, ComboboxLoadMoreItem } from "@/shared/components/ui/combobox";

import { render } from "../../../../tests/components/render";

function renderPaginatedList({
  hasNextPage = true,
  isFetchingNextPage = false,
  onLoadMore = vi.fn(),
  onSelectItem = vi.fn(),
}: {
  hasNextPage?: boolean;
  isFetchingNextPage?: boolean;
  onLoadMore?: () => void;
  onSelectItem?: () => void;
} = {}) {
  return render(
    <ComboboxList>
      <ComboboxItem value="router-1" onSelect={onSelectItem}>
        router-1
      </ComboboxItem>
      <ComboboxLoadMoreItem
        hasNextPage={hasNextPage}
        isFetchingNextPage={isFetchingNextPage}
        onLoadMore={onLoadMore}
      />
    </ComboboxList>
  );
}

describe("ComboboxLoadMoreItem", () => {
  it("renders no Load more option when there is no next page", async () => {
    // GIVEN
    const hasNextPage = false;

    // WHEN
    const component = await renderPaginatedList({ hasNextPage });

    // THEN
    await expect.element(component.getByRole("option", { name: "router-1" })).toBeVisible();
    await expect
      .element(component.getByRole("option", { name: "Load more" }))
      .not.toBeInTheDocument();
  });

  it("loads the next page when the Load more option is clicked", async () => {
    // GIVEN
    const onLoadMore = vi.fn();
    const component = await renderPaginatedList({ onLoadMore });

    // WHEN
    await component.getByRole("option", { name: "Load more" }).click();

    // THEN
    expect(onLoadMore).toHaveBeenCalledOnce();
    expect(onLoadMore).toHaveBeenCalledWith();
  });

  it("loads the next page when the Load more option is chosen with the arrow keys", async () => {
    // GIVEN
    const onLoadMore = vi.fn();
    const onSelectItem = vi.fn();
    const component = await renderPaginatedList({ onLoadMore, onSelectItem });
    await component.getByRole("combobox").click();

    // WHEN
    await userEvent.keyboard("{ArrowDown}{Enter}");

    // THEN
    expect(onLoadMore).toHaveBeenCalledOnce();
    expect(onSelectItem).not.toHaveBeenCalled();
  });

  it("shows a disabled Loading more... option while the next page loads", async () => {
    // GIVEN
    const isFetchingNextPage = true;

    // WHEN
    const component = await renderPaginatedList({ isFetchingNextPage });

    // THEN
    await expect
      .element(component.getByRole("option", { name: "Loading more..." }))
      .toHaveAttribute("aria-disabled", "true");
    await expect
      .element(component.getByRole("option", { name: "Load more" }))
      .not.toBeInTheDocument();
  });

  it("ignores clicks while the next page loads", async () => {
    // GIVEN
    const onLoadMore = vi.fn();
    const component = await renderPaginatedList({ isFetchingNextPage: true, onLoadMore });

    // WHEN
    await component.getByRole("option", { name: "Loading more..." }).click({ force: true });

    // THEN
    expect(onLoadMore).not.toHaveBeenCalled();
  });

  it("renders the Load more option in the accent color of the dark theme", async () => {
    // GIVEN
    document.documentElement.classList.add("dark");
    onTestFinished(() => document.documentElement.classList.remove("dark"));
    const darkAccent = getComputedStyle(document.documentElement).getPropertyValue("--accent");

    // WHEN
    const component = await renderPaginatedList();

    // THEN
    await expect
      .element(component.getByRole("option", { name: "Load more" }))
      .toHaveStyle({ color: darkAccent });
  });
});
