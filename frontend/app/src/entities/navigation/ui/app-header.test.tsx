import { afterEach, describe, expect, test, vi } from "vitest";

import { AppHeader } from "@/entities/navigation/ui/app-header";
import { RepositorySyncStatus } from "@/entities/repository/ui/repository-sync-status";
import { TaskStatus } from "@/entities/tasks/ui/task-status";

import { render } from "../../../../tests/components/render";

vi.mock("@/entities/repository/ui/repository-sync-status");
vi.mock("@/entities/tasks/ui/task-status");
vi.mock("@/entities/branches/ui/branch-selector");
vi.mock("@/entities/navigation/ui/time-selector");
vi.mock("@/entities/navigation/ui/breadcrumbs/breadcrumb-navigation");

describe("AppHeader", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  test("mounts the repository sync status indicator alongside the task status indicator", async () => {
    // GIVEN
    vi.mocked(RepositorySyncStatus).mockReturnValue(
      <div data-testid="sync-status-stub">sync status</div>
    );
    vi.mocked(TaskStatus).mockReturnValue(<div data-testid="task-status-stub">task status</div>);

    // WHEN
    const component = await render(<AppHeader />);

    // THEN
    await expect.element(component.getByTestId("sync-status-stub")).toBeVisible();
    await expect.element(component.getByTestId("task-status-stub")).toBeVisible();
  });

  test("puts the repository sync status indicator last in the bar", async () => {
    // GIVEN
    vi.mocked(RepositorySyncStatus).mockReturnValue(
      <div data-testid="sync-status-stub">sync status</div>
    );
    vi.mocked(TaskStatus).mockReturnValue(<div data-testid="task-status-stub">task status</div>);

    // WHEN
    const component = await render(<AppHeader />);

    // THEN
    const indicators = [...component.container.querySelectorAll("[data-testid$='-status-stub']")];
    expect(indicators.map((el) => el.getAttribute("data-testid"))).toEqual([
      "task-status-stub",
      "sync-status-stub",
    ]);
  });
});
