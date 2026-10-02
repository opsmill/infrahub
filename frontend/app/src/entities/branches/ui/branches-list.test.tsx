import { QueryClient, useIsFetching } from "@tanstack/react-query";
import { afterEach, describe, expect, test, vi } from "vitest";

import BranchesList from "@/entities/branches/ui/branches-list";
import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

import { render } from "../../../../tests/components/render";

vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-query")>();
  return { ...actual, useIsFetching: vi.fn(() => 0) };
});

vi.mock("@/entities/branches/ui/branches-table/branches-table", () => ({
  BranchesTable: () => <div>branches table</div>,
}));

vi.mock("@/entities/branches/ui/queries/get-branches-count.query", () => ({
  useGetBranchesCount: () => ({ data: 3, isPending: false, isRefetching: false, isError: false }),
}));

vi.mock("@/entities/nodes/filters/ui/hooks/use-filters", () => ({
  useFilters: () => [[], vi.fn()],
}));

// Retry renders a bare clickable div with no role or accessible name.
const findReloadControl = (container: HTMLElement) =>
  container.querySelector<HTMLElement>(':has(> iconify-icon[icon="mdi:reload"])');

afterEach(() => {
  vi.restoreAllMocks();
});

describe("BranchesList", () => {
  test("reloading refreshes both branches and repositories", async () => {
    // GIVEN
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");
    const { container } = await render(<BranchesList />);
    const reloadControl = findReloadControl(container);
    expect(reloadControl).not.toBeNull();

    // WHEN
    reloadControl?.click();

    // THEN
    await expect
      .poll(() => invalidateSpy)
      .toHaveBeenCalledWith({ queryKey: branchesQueryKeys.all });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: repositoryQueryKeys.all });
  });

  test("keeps the reload indicator busy while repositories are still refreshing", async () => {
    // GIVEN
    vi.mocked(useIsFetching).mockReturnValue(1);

    // WHEN
    const { container } = await render(<BranchesList />);

    // THEN
    expect(useIsFetching).toHaveBeenCalledWith({ queryKey: repositoryQueryKeys.all });
    expect(findReloadControl(container)?.className).toContain("animate-spin");
  });
});
