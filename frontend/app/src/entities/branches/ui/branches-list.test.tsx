import { QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, test, vi } from "vitest";

import BranchesList from "@/entities/branches/ui/branches-list";
import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

import { render } from "../../../../tests/components/render";

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

  test("keeps the reload indicator busy until both refreshes finish, and only for a reload", async () => {
    // GIVEN
    const pending: Array<() => void> = [];
    vi.spyOn(QueryClient.prototype, "invalidateQueries").mockImplementation(
      () => new Promise<void>((resolve) => pending.push(resolve))
    );
    const { container } = await render(<BranchesList />);
    expect(findReloadControl(container)?.className).not.toContain("animate-spin");

    // WHEN
    findReloadControl(container)?.click();

    // THEN
    await expect.poll(() => findReloadControl(container)?.className).toContain("animate-spin");
    for (const resolve of pending) resolve();
    await expect.poll(() => findReloadControl(container)?.className).not.toContain("animate-spin");
  });
});
