import { describe, expect, test, vi } from "vitest";

import { queryClient } from "@/shared/api/rest/client";

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

describe("BranchesList", () => {
  test("reloading refreshes both branches and repositories", async () => {
    // GIVEN
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries").mockResolvedValue();
    const { container } = await render(<BranchesList />);
    // Retry renders a bare clickable div with no role or accessible name.
    const reloadControl = container.querySelector<HTMLElement>(
      ':has(> iconify-icon[icon="mdi:reload"])'
    );
    expect(reloadControl).not.toBeNull();

    // WHEN
    reloadControl?.click();

    // THEN
    await expect
      .poll(() => invalidateSpy)
      .toHaveBeenCalledWith({ queryKey: branchesQueryKeys.all });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: repositoryQueryKeys.all });
  });
});
