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
  render(
    <TasksTable
      tasks={[task]}
      relatedNames={new Map()}
      emptyRelatedLabel="This branch"
      {...props}
    />
  );

describe("TasksTable", () => {
  beforeEach(() => {
    vi.mocked(useSchema).mockReturnValue({ schema: null } as unknown as ReturnType<
      typeof useSchema
    >);
  });

  test("shows the title, state, workflow label, related node and update time", async () => {
    const component = await renderTable();

    const headers = component.getByRole("columnheader").elements();
    expect(headers.map((h) => h.textContent)).toEqual([
      "Title",
      "State",
      "Workflow",
      "Related",
      "Updated",
    ]);
    await expect
      .element(component.getByRole("cell", { name: "Import", exact: true }))
      .toBeVisible();
  });

  test("uses the caller's label for a task with no related node", async () => {
    const component = await renderTable({ emptyRelatedLabel: "Nothing related" });

    await expect.element(component.getByRole("cell", { name: "Nothing related" })).toBeVisible();
  });

  test("names a related node from the names given", async () => {
    const component = await renderTable({
      tasks: [{ ...task, relatedNodes: [{ id: "repo-1", kind: "CoreRepository" }] }],
      relatedNames: new Map([["repo-1", "infrastructure-templates"]]),
    });

    await expect
      .element(component.getByRole("cell", { name: "infrastructure-templates" }))
      .toBeVisible();
  });

  test("links the title to the task details page", async () => {
    const component = await renderTable();

    await expect
      .element(component.getByRole("link", { name: task.title }))
      .toHaveAttribute("href", expect.stringContaining("/tasks/task-1"));
  });
});
