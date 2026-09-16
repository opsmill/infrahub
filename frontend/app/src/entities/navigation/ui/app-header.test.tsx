import { afterEach, describe, expect, test, vi } from "vitest";

import { AppHeader } from "@/entities/navigation/ui/app-header";
import { GitStatus } from "@/entities/repository/ui/git-status";
import { TaskStatus } from "@/entities/tasks/ui/task-status";

import { render } from "../../../../tests/components/render";

vi.mock("@/entities/repository/ui/git-status");
vi.mock("@/entities/tasks/ui/task-status");
vi.mock("@/entities/branches/ui/branch-selector");
vi.mock("@/entities/navigation/ui/time-selector");
vi.mock("@/entities/navigation/ui/breadcrumbs/breadcrumb-navigation");

describe("AppHeader", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  test("mounts the Git status indicator alongside the task status indicator", async () => {
    // GIVEN
    vi.mocked(GitStatus).mockReturnValue(<div data-testid="git-status-stub">git status</div>);
    vi.mocked(TaskStatus).mockReturnValue(<div data-testid="task-status-stub">task status</div>);

    // WHEN
    const component = await render(<AppHeader />);

    // THEN
    await expect.element(component.getByTestId("git-status-stub")).toBeVisible();
    await expect.element(component.getByTestId("task-status-stub")).toBeVisible();
  });

  test("puts the Git status indicator last in the bar", async () => {
    // GIVEN
    vi.mocked(GitStatus).mockReturnValue(<div data-testid="git-status-stub">git status</div>);
    vi.mocked(TaskStatus).mockReturnValue(<div data-testid="task-status-stub">task status</div>);

    // WHEN
    const component = await render(<AppHeader />);

    // THEN
    const indicators = [...component.container.querySelectorAll("[data-testid$='-status-stub']")];
    expect(indicators.map((el) => el.getAttribute("data-testid"))).toEqual([
      "task-status-stub",
      "git-status-stub",
    ]);
  });
});
