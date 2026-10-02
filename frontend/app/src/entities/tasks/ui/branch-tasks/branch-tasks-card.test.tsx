import { useState } from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import type { TaskListItem, TaskListPage } from "@/entities/tasks/domain/model/task-list-item";
import {
  useGetBranchFailedTaskCount,
  useGetBranchTasks,
} from "@/entities/tasks/ui/queries/get-branch-tasks.query";

import { render } from "../../../../../tests/components/render";
import { BranchTasksCard } from "./branch-tasks-card";

vi.mock("@/entities/tasks/ui/queries/get-branch-tasks.query");
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

const generatePage = (count: number, tasks?: TaskListItem[]): TaskListPage => ({
  tasks: tasks ?? Array.from({ length: Math.min(count, 10) }, (_, index) => generateTask(index)),
  count,
});

type QueryState = { data?: TaskListPage; isPending?: boolean; failedCount?: number };

const mockQueries = ({ data, isPending = false, failedCount = 0 }: QueryState) => {
  vi.mocked(useGetBranchTasks).mockReturnValue({
    data,
    isPending,
  } as unknown as ReturnType<typeof useGetBranchTasks>);
  vi.mocked(useGetBranchFailedTaskCount).mockReturnValue({
    data: isPending ? undefined : failedCount,
  } as unknown as ReturnType<typeof useGetBranchFailedTaskCount>);
};

const renderCard = (props: Partial<Parameters<typeof BranchTasksCard>[0]> = {}) =>
  render(
    <BranchTasksCard
      branchName="feature"
      isDefaultBranch={false}
      page={1}
      onPageChange={vi.fn()}
      repositoryNames={new Map()}
      {...props}
    />
  );

function StatefulCard({
  initialPage,
  onPageChange,
}: {
  initialPage: number;
  onPageChange: (page: number) => void;
}) {
  const [page, setPage] = useState(initialPage);
  return (
    <BranchTasksCard
      branchName="feature"
      isDefaultBranch={false}
      page={page}
      onPageChange={(next) => {
        onPageChange(next);
        setPage(next);
      }}
      repositoryNames={new Map()}
    />
  );
}

const mockPagedTasks = (count: number) => {
  vi.mocked(useGetBranchTasks).mockImplementation(({ page }) => {
    const first = (page - 1) * 10;
    const tasks =
      first >= 0 && first < count
        ? Array.from({ length: Math.min(10, count - first) }, (_, index) =>
            generateTask(first + index)
          )
        : [];
    return { data: { tasks, count }, isPending: false } as unknown as ReturnType<
      typeof useGetBranchTasks
    >;
  });
  vi.mocked(useGetBranchFailedTaskCount).mockReturnValue({
    data: 0,
  } as unknown as ReturnType<typeof useGetBranchFailedTaskCount>);
};

const bodyRows = (container: HTMLElement) => [...container.querySelectorAll("tbody tr")];

const cellText = (container: HTMLElement, rowIndex: number, cellIndex: number) =>
  bodyRows(container)[rowIndex]?.querySelectorAll("td")[cellIndex]?.textContent;

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
    initialUrl = window.location.href;
    window.history.replaceState(null, "", "/branches/feature?branch=main");
  });

  afterEach(() => {
    window.history.replaceState(null, "", initialUrl);
  });

  test("shows the 10 most recent tasks, a pager, the total and the failed count", async () => {
    // GIVEN
    mockQueries({ data: generatePage(12), failedCount: 1 });

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("Tasks", { exact: true })).toBeVisible();
    expect(bodyRows(component.container)).toHaveLength(10);
    await expect.element(component.getByText("12", { exact: true }).first()).toBeVisible();
    await expect.element(component.getByRole("link", { name: "1 failed" })).toBeVisible();
    await expect
      .element(component.getByRole("navigation", { name: "Tasks pagination" }))
      .toBeVisible();
  });

  test("hides the failed count when no task failed", async () => {
    // GIVEN
    mockQueries({ data: generatePage(3), failedCount: 0 });

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("3", { exact: true })).toBeVisible();
    expect(component.container.textContent).not.toContain("failed");
    expect(component.container.querySelector("nav")).toBeNull();
  });

  test("links each title to its task details page", async () => {
    // GIVEN
    mockQueries({ data: generatePage(1, [generateTask(1, { id: "abc-123", title: "Validate" })]) });

    // WHEN
    const component = await renderCard();

    // THEN
    const link = component.getByRole("link", { name: "Validate" });
    await expect.element(link).toHaveAttribute("href", "/tasks/abc-123?branch=main");
    await expect.element(link).toHaveAttribute("title", "Validate");
  });

  test("shows the repository name, 'This branch', or the object kind in Related", async () => {
    // GIVEN
    mockQueries({
      data: generatePage(3, [
        generateTask(1, { relatedNodes: [{ id: "repo-1", kind: "CoreRepository" }] }),
        generateTask(2, { relatedNodes: [] }),
        generateTask(3, { relatedNodes: [{ id: "art-1", kind: "CoreArtifactDefinition" }] }),
      ]),
    });

    // WHEN
    const component = await renderCard({
      repositoryNames: new Map([["repo-1", "infrastructure-templates"]]),
    });

    // THEN
    expect(cellText(component.container, 0, 3)).toBe("infrastructure-templates");
    expect(cellText(component.container, 1, 3)).toBe("This branch");
    expect(cellText(component.container, 2, 3)).toBe("Artifact Definition");
  });

  test("shows a short workflow label when known, a readable identifier otherwise", async () => {
    // GIVEN
    mockQueries({
      data: generatePage(2, [
        generateTask(1, { workflow: "generator-definition-run" }),
        generateTask(2, { workflow: "custom-workflow" }),
      ]),
    });

    // WHEN
    const component = await renderCard();

    // THEN
    expect(cellText(component.container, 0, 2)).toBe("Generator");
    expect(cellText(component.container, 1, 2)).toBe("Custom workflow");
  });

  test("tints failed rows and shows the state badge, UNKNOWN when missing", async () => {
    // GIVEN
    mockQueries({
      data: generatePage(3, [
        generateTask(1, { state: "FAILED" }),
        generateTask(2, { state: "COMPLETED" }),
        generateTask(3, { state: null }),
      ]),
    });

    // WHEN
    const component = await renderCard();

    // THEN
    const rows = bodyRows(component.container);
    expect(rows[0]?.classList).toContain("bg-danger-surface");
    expect(rows[1]?.classList).not.toContain("bg-danger-surface");
    expect(cellText(component.container, 0, 1)).toBe("FAILED");
    expect(cellText(component.container, 2, 1)).toBe("UNKNOWN");
  });

  test("shows placeholder rows and no count while loading", async () => {
    // GIVEN
    mockQueries({ isPending: true });

    // WHEN
    const component = await renderCard();

    // THEN
    const status = component.getByRole("status");
    await expect.element(status).toHaveAttribute("aria-busy", "true");
    await expect.element(status).toHaveTextContent("Loading tasks");
    expect(status.element().querySelectorAll(".h-10")).toHaveLength(3);
    expect(component.container.querySelector("tbody")).toBeNull();
    expect(component.container.querySelector(".rounded-full")).toBeNull();
  });

  test("explains what will appear when no task has run", async () => {
    // GIVEN
    mockQueries({ data: generatePage(0) });

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
    mockQueries({ data: undefined });

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("Task results didn't load.")).toBeVisible();
  });

  test("keeps the table height on a short page 2", async () => {
    // GIVEN
    mockQueries({ data: generatePage(11, [generateTask(10)]) });

    // WHEN
    const component = await renderCard({ page: 2 });

    // THEN
    expect(bodyRows(component.container)).toHaveLength(1);
    await expect.element(component.getByTestId("tasks-table")).toHaveStyle({ minHeight: "440px" });
    await expect
      .element(component.getByRole("navigation", { name: "Tasks pagination" }))
      .toBeVisible();
  });

  test("asks for the next page through the pager", async () => {
    // GIVEN
    const onPageChange = vi.fn();
    mockQueries({ data: generatePage(12) });
    const component = await renderCard({ onPageChange });

    // WHEN
    await component.getByRole("button", { name: "Next page" }).click();

    // THEN
    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  test("passes the requested page and the branch to its queries", async () => {
    // GIVEN
    mockQueries({ data: generatePage(11, [generateTask(10)]) });

    // WHEN
    await renderCard({ page: 2 });

    // THEN
    expect(vi.mocked(useGetBranchTasks)).toHaveBeenCalledWith({ branchName: "feature", page: 2 });
    expect(vi.mocked(useGetBranchFailedTaskCount)).toHaveBeenCalledWith({ branchName: "feature" });
  });

  test("moves a page past the end to the last page and shows its rows", async () => {
    // GIVEN
    const onPageChange = vi.fn();
    mockPagedTasks(12);

    // WHEN
    const component = await render(<StatefulCard initialPage={99} onPageChange={onPageChange} />);

    // THEN
    await expect.element(component.getByText("Task 11", { exact: true })).toBeVisible();
    expect(onPageChange).toHaveBeenCalledWith(2);
    expect(vi.mocked(useGetBranchTasks)).toHaveBeenLastCalledWith({
      branchName: "feature",
      page: 2,
    });
    expect(bodyRows(component.container)).toHaveLength(2);
    await expect
      .element(component.getByRole("button", { name: "Page 2" }))
      .toHaveAttribute("aria-current", "page");
  });

  test("moves a page below 1 to page 1", async () => {
    // GIVEN
    const onPageChange = vi.fn();
    mockPagedTasks(12);

    // WHEN
    const component = await render(<StatefulCard initialPage={0} onPageChange={onPageChange} />);

    // THEN
    await expect.element(component.getByText("Task 0", { exact: true })).toBeVisible();
    expect(onPageChange).toHaveBeenCalledWith(1);
    expect(vi.mocked(useGetBranchTasks)).toHaveBeenLastCalledWith({
      branchName: "feature",
      page: 1,
    });
    expect(bodyRows(component.container)).toHaveLength(10);
  });

  test("leaves a page in range as it is", async () => {
    // GIVEN
    const onPageChange = vi.fn();
    mockPagedTasks(12);

    // WHEN
    const component = await render(<StatefulCard initialPage={2} onPageChange={onPageChange} />);

    // THEN
    await expect.element(component.getByText("Task 11", { exact: true })).toBeVisible();
    expect(onPageChange).not.toHaveBeenCalled();
  });

  test("opens the Tasks page on the page's branch, not the selector's", async () => {
    // GIVEN
    mockQueries({ data: generatePage(12), failedCount: 2 });

    // WHEN
    const component = await renderCard();

    // THEN
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

  test("uses no hard-coded hex colour in class names", async () => {
    // GIVEN
    mockQueries({ data: generatePage(2, [generateTask(1, { state: "FAILED" }), generateTask(2)]) });

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("FAILED")).toBeVisible();
    const classes = [...component.container.querySelectorAll("[class]")].map(
      (element) => element.getAttribute("class") ?? ""
    );
    expect(classes.filter((value) => /#[0-9a-f]{3,8}\b/i.test(value))).toEqual([]);
  });
});
