import { afterEach, describe, expect, test, vi } from "vitest";

import { AppHeader } from "@/entities/navigation/ui/app-header";
import { GitStatus } from "@/entities/repository/ui/git-status";
import { TaskStatus } from "@/entities/tasks/ui/task-status";

import { render } from "../../../../tests/components/render";

// The header composes these; each has its own suite, so stub them here and assert only that
// the header mounts both. Rendering the real subtrees would duplicate that coverage.
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
    // GIVEN both header indicators are available
    vi.mocked(GitStatus).mockReturnValue(<div data-testid="git-status-stub">git status</div>);
    vi.mocked(TaskStatus).mockReturnValue(<div data-testid="task-status-stub">task status</div>);

    // WHEN
    const component = await render(<AppHeader />);

    // THEN both are present: they answer different questions and neither replaces the other
    await expect.element(component.getByTestId("git-status-stub")).toBeVisible();
    await expect.element(component.getByTestId("task-status-stub")).toBeVisible();
  });

  test("puts the Git status indicator last in the bar", async () => {
    // GIVEN
    vi.mocked(GitStatus).mockReturnValue(<div data-testid="git-status-stub">git status</div>);
    vi.mocked(TaskStatus).mockReturnValue(<div data-testid="task-status-stub">task status</div>);

    // WHEN
    const component = await render(<AppHeader />);

    // THEN it takes the edge slot, after the task indicator. The order is a design decision —
    // the bar reads in severity order and the control that must be noticed from any page sits
    // at the edge — so it is pinned rather than left to whichever import happens to come first.
    const task = component.container.querySelector('[data-testid="task-status-stub"]');
    const git = component.container.querySelector('[data-testid="git-status-stub"]');
    expect(
      task?.compareDocumentPosition(git as Node) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
  });
});
