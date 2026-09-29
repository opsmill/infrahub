import { beforeEach, describe, expect, test, vi } from "vitest";

import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import type { TaskListItem } from "@/entities/tasks/domain/model/task-list-item";

import { render } from "../../../../../tests/components/render";
import { TasksTable } from "./tasks-table";

vi.mock("@/entities/schema/ui/hooks/useSchema");

const task: TaskListItem = {
  id: "task-1",
  title: "Import objects from git repository",
  branch: "ple-branch",
  state: "FAILED",
  workflow: "git-repository-import-object",
  relatedNodes: [],
  updatedAt: "2026-09-01T10:00:00Z",
};

const renderTable = (props: Partial<Parameters<typeof TasksTable>[0]> = {}) =>
  render(<TasksTable tasks={[task]} totalCount={1} page={1} onPageChange={() => {}} {...props} />);

describe("TasksTable", () => {
  beforeEach(() => {
    vi.mocked(useSchema).mockReturnValue({ schema: null } as unknown as ReturnType<
      typeof useSchema
    >);
  });

  test("shows every column by default, with the branch and the workflow label", async () => {
    const component = await renderTable();

    for (const header of ["Title", "Branch", "State", "Workflow", "Related", "Updated"]) {
      await expect.element(component.getByRole("columnheader", { name: header })).toBeVisible();
    }
    await expect.element(component.getByRole("cell", { name: "ple-branch" })).toBeVisible();
    await expect.element(component.getByRole("cell", { name: "Import", exact: true })).toBeVisible();
    await expect.element(component.getByRole("cell", { name: "—" })).toBeVisible();
  });

  test("shows only the requested columns, in order", async () => {
    const component = await renderTable({ columns: ["title", "state"] });

    const headers = component.getByRole("columnheader").elements();
    expect(headers.map((h) => h.textContent)).toEqual(["Title", "State"]);
  });

  test("uses the caller's label for a task with no related node", async () => {
    const component = await renderTable({ emptyRelatedLabel: "This branch" });

    await expect.element(component.getByRole("cell", { name: "This branch" })).toBeVisible();
  });

  test("links the title to the task details page", async () => {
    const component = await renderTable();

    await expect
      .element(component.getByRole("link", { name: task.title }))
      .toHaveAttribute("href", expect.stringContaining("/tasks/task-1"));
  });
});
