import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { getRepositoryNames } from "@/entities/repository/domain/use-cases/get-repository-names";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import type { TaskListItem } from "@/entities/tasks/domain/model/task-list-item";
import { getBranchTasks } from "@/entities/tasks/domain/use-cases/get-branch-tasks";
import { getTaskCount } from "@/entities/tasks/domain/use-cases/get-task-count";

import { render } from "../../../../../tests/components/render";
import { BranchTasksCard } from "./branch-tasks-card";

vi.mock("@/entities/tasks/domain/use-cases/get-branch-tasks");
vi.mock("@/entities/tasks/domain/use-cases/get-task-count");
vi.mock("@/entities/repository/domain/use-cases/get-repository-names");
vi.mock("@/entities/schema/ui/hooks/useSchema");

const KIND_LABELS: Record<string, string> = { CoreArtifactDefinition: "Artifact Definition" };

const generateTask = (index: number, overrides: Partial<TaskListItem> = {}): TaskListItem => ({
  id: `task-${index}`,
  title: `Task ${index}`,
  branch: "ple-branch",
  state: "COMPLETED",
  workflow: "branch-validate",
  relatedNodes: [],
  updatedAt: "2026-09-01T10:00:00Z",
  ...overrides,
});

const generateTasks = (count: number) =>
  Array.from({ length: count }, (_, index) => generateTask(index));

const serve = (tasks: TaskListItem[], { failedCount = 0 } = {}) => {
  vi.mocked(getBranchTasks).mockImplementation(async ({ offset, limit }) => ({
    tasks: tasks.slice(offset, offset + limit),
    count: tasks.length,
  }));
  vi.mocked(getTaskCount).mockResolvedValue(failedCount);
};

const renderCard = (search = "") => {
  window.history.replaceState(null, "", `/branches/feature?branch=main${search}`);
  return render(<BranchTasksCard branchName="feature" />);
};

const bodyRows = (container: HTMLElement) => [...container.querySelectorAll("tbody tr")];

const cellText = (container: HTMLElement, rowIndex: number, cellIndex: number) =>
  bodyRows(container)[rowIndex]?.querySelectorAll("td")[cellIndex]?.textContent;

const requestedOffsets = () =>
  vi.mocked(getBranchTasks).mock.calls.map(([params]) => params.offset);

describe("BranchTasksCard", () => {
  let initialUrl: string;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useSchema).mockImplementation(
      (kind) =>
        ({
          schema: kind && KIND_LABELS[kind] ? { label: KIND_LABELS[kind] } : null,
        }) as unknown as ReturnType<typeof useSchema>
    );
    vi.mocked(getRepositoryNames).mockResolvedValue({});
    initialUrl = window.location.href;
  });

  afterEach(() => {
    window.history.replaceState(null, "", initialUrl);
  });

  test("shows the 10 most recent tasks, a pager, the total and the failed count", async () => {
    // GIVEN
    serve(generateTasks(12), { failedCount: 1 });

    // WHEN
    const component = await renderCard();

    // THEN
    await expect
      .element(component.getByRole("navigation", { name: "Tasks pagination" }))
      .toBeVisible();
    await expect.element(component.getByText("Tasks", { exact: true })).toBeVisible();
    expect(bodyRows(component.container)).toHaveLength(10);
    await expect.element(component.getByText("12 tasks", { exact: true })).toBeVisible();
    await expect.element(component.getByRole("link", { name: "1 failed" })).toBeVisible();
  });

  test("hides the failed count when no task failed", async () => {
    // GIVEN
    serve(generateTasks(3));

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("3 tasks", { exact: true })).toBeVisible();
    expect(component.container.textContent).not.toContain("failed");
    expect(component.container.querySelector("nav")).toBeNull();
  });

  test("links each title to its task details page", async () => {
    // GIVEN
    serve([generateTask(1, { id: "abc-123", title: "Validate" })]);

    // WHEN
    const component = await renderCard();

    // THEN
    const link = component.getByRole("link", { name: "Validate" });
    await expect.element(link).toHaveAttribute("href", "/tasks/abc-123?branch=main");
    await expect.element(link).toHaveAttribute("title", "Validate");
  });

  test("shows the repository name, 'This branch', or the object kind in Related", async () => {
    // GIVEN
    serve([
      generateTask(1, { relatedNodes: [{ id: "repo-1", kind: "CoreRepository" }] }),
      generateTask(2, { relatedNodes: [] }),
      generateTask(3, { relatedNodes: [{ id: "art-1", kind: "CoreArtifactDefinition" }] }),
    ]);
    vi.mocked(getRepositoryNames).mockResolvedValue({ "repo-1": "infrastructure-templates" });

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("infrastructure-templates")).toBeVisible();
    expect(cellText(component.container, 0, 3)).toBe("infrastructure-templates");
    expect(cellText(component.container, 1, 3)).toBe("This branch");
    expect(cellText(component.container, 2, 3)).toBe("Artifact Definition");
  });

  test("looks up only the related nodes of the page shown, on the page's branch", async () => {
    // GIVEN
    serve([
      generateTask(1, { relatedNodes: [{ id: "repo-2", kind: "CoreRepository" }] }),
      generateTask(2, {
        relatedNodes: [
          { id: "repo-1", kind: "CoreReadOnlyRepository" },
          { id: "repo-2", kind: "CoreRepository" },
        ],
      }),
    ]);

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("Task 1")).toBeVisible();
    expect(getRepositoryNames).toHaveBeenCalledTimes(1);
    expect(getRepositoryNames).toHaveBeenCalledWith({
      branchName: "feature",
      ids: ["repo-1", "repo-2"],
    });
  });

  test("keeps the task rows and count when the repository names can't be read", async () => {
    // GIVEN
    serve([
      generateTask(1, { relatedNodes: [{ id: "repo-1", kind: "CoreRepository" }] }),
      generateTask(2),
    ]);
    vi.mocked(getRepositoryNames).mockRejectedValue(new Error("Permission denied"));

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("Task 1")).toBeVisible();
    await expect.element(component.getByText("Task 2")).toBeVisible();
    await expect.element(component.getByText("2 tasks", { exact: true })).toBeVisible();
    expect(cellText(component.container, 0, 3)).toBe("CoreRepository");
  });

  test("doesn't look up names when no task on the page has a related node", async () => {
    // GIVEN
    serve(generateTasks(2));

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("Task 1")).toBeVisible();
    expect(getRepositoryNames).not.toHaveBeenCalled();
  });

  test("shows a short workflow label when known, a readable identifier otherwise", async () => {
    // GIVEN
    serve([
      generateTask(1, { workflow: "generator-definition-run" }),
      generateTask(2, { workflow: "custom-workflow" }),
    ]);

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("Generator")).toBeVisible();
    expect(cellText(component.container, 0, 2)).toBe("Generator");
    expect(cellText(component.container, 1, 2)).toBe("Custom workflow");
  });

  test("tints failed rows and shows the state badge, UNKNOWN when missing", async () => {
    // GIVEN
    serve([
      generateTask(1, { state: "FAILED" }),
      generateTask(2, { state: "COMPLETED" }),
      generateTask(3, { state: null }),
    ]);

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("UNKNOWN")).toBeVisible();
    const rows = bodyRows(component.container);
    expect(rows[0]?.classList).toContain("bg-danger-surface");
    expect(rows[1]?.classList).not.toContain("bg-danger-surface");
    expect(cellText(component.container, 0, 1)).toBe("FAILED");
    expect(cellText(component.container, 2, 1)).toBe("UNKNOWN");
  });

  test("shows placeholder rows and no count while loading", async () => {
    // GIVEN
    vi.mocked(getBranchTasks).mockReturnValue(new Promise(() => {}));
    vi.mocked(getTaskCount).mockReturnValue(new Promise(() => {}));

    // WHEN
    const component = await renderCard();

    // THEN
    const status = component.getByRole("status");
    await expect.element(status).toHaveAttribute("aria-busy", "true");
    await expect.element(status).toHaveTextContent("Loading tasks");
    expect(status.element().querySelectorAll(".h-10")).toHaveLength(3);
    expect(component.container.querySelector("tbody")).toBeNull();
    expect(component.getByText(/^\d+ tasks?$/).query()).toBeNull();
  });

  test("explains what will appear when no task has run", async () => {
    // GIVEN
    serve([]);

    // WHEN
    const component = await renderCard();

    // THEN
    await expect
      .element(component.getByText(/No tasks have run on this branch yet\. Imports, generators/))
      .toBeVisible();
    expect(component.container.querySelector("tbody")).toBeNull();
  });

  test("says the task results didn't load when the query fails", async () => {
    // GIVEN
    vi.mocked(getBranchTasks).mockRejectedValue(new Error("Something broke"));
    vi.mocked(getTaskCount).mockResolvedValue(0);

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("Task results didn't load.")).toBeVisible();
  });

  test("offers the first page when a later page fails, as the pager came with the page", async () => {
    // GIVEN
    const tasks = generateTasks(11);
    serve(tasks);
    vi.mocked(getBranchTasks).mockImplementation(async ({ offset, limit }) => {
      if (offset > 0) throw new Error("Something broke");
      return { tasks: tasks.slice(offset, offset + limit), count: tasks.length };
    });
    const component = await renderCard("&tasks_page=2");
    await expect.element(component.getByText("Task results didn't load.")).toBeVisible();

    // WHEN
    await component.getByRole("button", { name: "Go to first page" }).click();

    // THEN
    await expect.poll(() => bodyRows(component.container)).toHaveLength(10);
    expect(new URL(window.location.href).searchParams.get("tasks_page")).toBeNull();
  });

  test("keeps the table height on a short page 2", async () => {
    // GIVEN
    serve(generateTasks(11));

    // WHEN
    const component = await renderCard("&tasks_page=2");

    // THEN
    await expect
      .element(component.getByRole("navigation", { name: "Tasks pagination" }))
      .toBeVisible();
    expect(bodyRows(component.container)).toHaveLength(1);
    await expect.element(component.getByTestId("tasks-table")).toHaveStyle({ minHeight: "440px" });
  });

  test("moves to the next page through the pager and puts it in the url", async () => {
    // GIVEN
    serve(generateTasks(12));
    const component = await renderCard();
    await expect.element(component.getByRole("button", { name: "Next page" })).toBeVisible();

    // WHEN
    await component.getByRole("button", { name: "Next page" }).click();

    // THEN
    await expect.element(component.getByText("Task 11", { exact: true })).toBeVisible();
    expect(new URL(window.location.href).searchParams.get("tasks_page")).toBe("2");
    expect(getBranchTasks).toHaveBeenLastCalledWith(
      { branchName: "feature", offset: 10, limit: 10 },
      { silenceErrors: true }
    );
    expect(getTaskCount).toHaveBeenCalledWith(
      { branchName: "feature", state: ["FAILED"] },
      { silenceErrors: true }
    );
  });

  test("says a page past the end doesn't exist, and goes to the last page on request", async () => {
    // GIVEN
    serve(generateTasks(12));
    const component = await renderCard("&tasks_page=99");
    await expect.element(component.getByText("Page 99 doesn't exist.")).toBeVisible();
    expect(bodyRows(component.container)).toHaveLength(0);
    expect(requestedOffsets()).toEqual([980]);

    // WHEN
    await component.getByRole("button", { name: "Go to last page" }).click();

    // THEN
    await expect.element(component.getByText("Task 11", { exact: true })).toBeVisible();
    expect(bodyRows(component.container)).toHaveLength(2);
    await expect
      .element(component.getByRole("button", { name: "Page 2" }))
      .toHaveAttribute("aria-current", "page");
    expect(new URL(window.location.href).searchParams.get("tasks_page")).toBe("2");
  });

  test("shows page 1 for a page below 1", async () => {
    // GIVEN
    serve(generateTasks(12));

    // WHEN
    const component = await renderCard("&tasks_page=0");

    // THEN
    await expect.element(component.getByText("Task 0", { exact: true })).toBeVisible();
    expect(bodyRows(component.container)).toHaveLength(10);
    expect(requestedOffsets()).toEqual([0]);
  });

  test("opens the Tasks page on the page's branch, not the selector's", async () => {
    // GIVEN
    serve(generateTasks(12), { failedCount: 2 });

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByRole("link", { name: "2 failed" })).toBeVisible();
    const openHref = component
      .getByRole("link", { name: "Open in Tasks" })
      .element()
      .getAttribute("href");
    const failedHref = component
      .getByRole("link", { name: "2 failed" })
      .element()
      .getAttribute("href");
    const openParams = new URL(openHref ?? "", window.location.origin).searchParams;
    const failedParams = new URL(failedHref ?? "", window.location.origin).searchParams;

    expect(openHref?.startsWith("/tasks?")).toBe(true);
    expect(openParams.get("branch")).toBe("feature");
    expect(JSON.parse(openParams.get("filters") ?? "[]")).toEqual([
      { name: "branch__value", value: "feature" },
    ]);
    expect(failedParams.get("branch")).toBe("feature");
    expect(JSON.parse(failedParams.get("filters") ?? "[]")).toEqual([
      { name: "branch__value", value: "feature" },
      { name: "state__value", value: "FAILED" },
    ]);
  });
});
