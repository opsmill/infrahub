import { QueryClient, useQueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, test, vi } from "vitest";

import { branchGitStatusQueryKeys } from "@/entities/branch-git-status/ui/queries/branch-git-status.query-keys";
import BranchesList from "@/entities/branches/ui/branches-list";
import { buildGitStatusRefreshNavigationState } from "@/entities/branches/ui/hooks/use-refresh-branch-git-status-on-task-end";
import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import { isTaskFinished } from "@/entities/tasks/domain/use-cases/is-task-finished";

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

vi.mock("@/entities/tasks/domain/use-cases/is-task-finished");

// The reload control is a clickable div with no role or accessible name.
const findReloadControl = (container: HTMLElement) =>
  container.querySelector<HTMLElement>(':has(> iconify-icon[icon="mdi:reload"])');

function CaptureQueryClient({ onClient }: { onClient: (client: QueryClient) => void }) {
  onClient(useQueryClient());
  return null;
}

afterEach(() => {
  window.history.replaceState(null, "");
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.resetAllMocks();
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
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: branchGitStatusQueryKeys.all });
  });

  test("keeps the reload indicator busy until both refreshes finish", async () => {
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
    await expect.poll(() => pending.length).toBe(2);
    pending[0]?.();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(findReloadControl(container)?.className).toContain("animate-spin");
    pending[1]?.();
    await expect.poll(() => findReloadControl(container)?.className).not.toContain("animate-spin");
  });

  test("does not spin the reload indicator for a background repository fetch", async () => {
    // GIVEN
    let client: QueryClient | undefined;
    const { container } = await render(
      <>
        <BranchesList />
        <CaptureQueryClient onClient={(c) => (client = c)} />
      </>
    );

    // WHEN
    client?.prefetchQuery({
      queryKey: [...branchGitStatusQueryKeys.all, "background"],
      queryFn: () => new Promise<never>(() => {}),
    });

    // THEN
    await expect.poll(() => client?.isFetching({ queryKey: branchGitStatusQueryKeys.all })).toBe(1);
    expect(findReloadControl(container)?.className).not.toContain("animate-spin");
  });

  test("refreshes the branch Git status once when the task it was opened for ends", async () => {
    // GIVEN the list is opened after a merge that ends on the second check
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(isTaskFinished).mockResolvedValueOnce(false).mockResolvedValue(true);
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");
    const gitStatusInvalidations = () =>
      invalidateSpy.mock.calls.filter(
        ([filters]) => filters?.queryKey === branchGitStatusQueryKeys.all
      ).length;
    window.history.replaceState(
      { usr: buildGitStatusRefreshNavigationState("task-1"), key: "merge", idx: 0 },
      ""
    );

    // WHEN the merge is still running
    await render(<BranchesList />);
    await expect.poll(() => vi.mocked(isTaskFinished).mock.calls.length).toBe(1);

    // THEN the Git status is left alone
    expect(isTaskFinished).toHaveBeenCalledWith({ taskId: "task-1" });
    expect(gitStatusInvalidations()).toBe(0);

    // WHEN the next check finds the merge ended
    await vi.advanceTimersByTimeAsync(5000);

    // THEN the Git status is refreshed once, and the task is gone from history
    await expect.poll(() => gitStatusInvalidations()).toBe(1);
    expect(window.history.state?.usr).toBeNull();
  });

  test("checks no task when opened without one", async () => {
    // WHEN
    await render(<BranchesList />);

    // THEN
    expect(isTaskFinished).not.toHaveBeenCalled();
  });
});
