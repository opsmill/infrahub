import { describe, expect, test, vi } from "vitest";

import { BranchMergeButton } from "@/entities/branches/ui/branch-merge-button";
import { useGetBranchDetails } from "@/entities/branches/ui/queries/get-branch-details.query";
import type { BranchRepositoriesResult } from "@/entities/repository/domain/model/branch-repository";
import { useGetBranchRepositories } from "@/entities/repository/ui/queries/get-branch-repositories.query";
import { useGetRepositoryImportError } from "@/entities/repository/ui/queries/get-repository-import-error.query";
import type { TaskListPage } from "@/entities/tasks/domain/model/task-list-item";
import {
  useGetBranchFailedTaskCount,
  useGetBranchTasks,
} from "@/entities/tasks/ui/queries/get-branch-tasks.query";

import { render } from "../../../../tests/components/render";
import { generateBranch } from "../../../../tests/fake/branch";
import { buildBranchRepositoriesScenario } from "../../../../tests/fake/branch-repositories";
import { BranchDetails } from "./branch-details";

vi.mock("@/entities/branches/ui/queries/get-branch-details.query");
vi.mock("@/entities/repository/ui/queries/get-branch-repositories.query");
vi.mock("@/entities/repository/ui/queries/get-repository-import-error.query");
vi.mock("@/entities/tasks/ui/queries/get-branch-tasks.query");
vi.mock("@/entities/branches/ui/branch-merge-button", () => ({
  BranchMergeButton: vi.fn(() => <button type="button">Merge</button>),
}));
vi.mock("@/entities/branches/ui/branch-propose-change-button", () => ({
  BranchProposeChangeButton: () => <button type="button">Propose change</button>,
}));
vi.mock("@/entities/branches/ui/branch-rebase-button", () => ({
  BranchRebaseButton: () => <button type="button">Rebase</button>,
}));
vi.mock("@/entities/branches/ui/branch-validate-button", () => ({
  BranchValidateButton: () => <button type="button">Validate</button>,
}));
vi.mock("@/entities/branches/ui/branch-delete-button", () => ({
  BranchDeleteButton: () => <button type="button">Delete</button>,
}));

const ACTION_BUTTONS = ["Merge", "Propose change", "Rebase", "Validate", "Delete"];

type RepositoriesState = { data?: BranchRepositoriesResult; isPending?: boolean };
type TasksState = { data?: TaskListPage; isPending?: boolean };

const LOADED_TASKS: TasksState = { data: { tasks: [], count: 0 } };

const setup = ({
  isDefault,
  repositories = { data: buildBranchRepositoriesScenario("all-clear") },
  tasks = LOADED_TASKS,
}: {
  isDefault: boolean;
  repositories?: RepositoriesState;
  tasks?: TasksState;
}) => {
  vi.clearAllMocks();
  const branch = generateBranch({ name: "feature", is_default: isDefault });
  vi.mocked(useGetBranchDetails).mockReturnValue({
    isPending: false,
    error: null,
    data: branch,
  } as unknown as ReturnType<typeof useGetBranchDetails>);
  vi.mocked(useGetBranchRepositories).mockReturnValue({
    isPending: false,
    isError: false,
    ...repositories,
  } as unknown as ReturnType<typeof useGetBranchRepositories>);
  vi.mocked(useGetRepositoryImportError).mockReturnValue({
    data: undefined,
  } as unknown as ReturnType<typeof useGetRepositoryImportError>);
  vi.mocked(useGetBranchTasks).mockReturnValue({
    isPending: false,
    ...tasks,
  } as unknown as ReturnType<typeof useGetBranchTasks>);
  vi.mocked(useGetBranchFailedTaskCount).mockReturnValue({
    data: 0,
  } as unknown as ReturnType<typeof useGetBranchFailedTaskCount>);
  return branch;
};

const renderDetails = () =>
  render(
    <BranchDetails
      branchName="feature"
      reposPage={1}
      onReposPageChange={vi.fn()}
      tasksPage={1}
      onTasksPageChange={vi.fn()}
    />
  );

const expectInDocumentOrder = ([first, ...rest]: Element[]) => {
  let previous = first;
  for (const current of rest) {
    expect(
      previous?.compareDocumentPosition(current),
      `expected to precede ${current.textContent?.slice(0, 40)}`
    ).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    previous = current;
  }
};

describe("BranchDetails", () => {
  test("on a non-default branch, renders Details, then Git repositories, then the action buttons, then Tasks", async () => {
    // GIVEN
    setup({ isDefault: false });

    // WHEN
    const component = await renderDetails();

    // THEN
    await expect.element(component.getByText("Details", { exact: true })).toBeVisible();
    await expect.element(component.getByTestId("branch-repositories-card")).toBeVisible();

    expectInDocumentOrder([
      component.getByText("Details", { exact: true }).element(),
      component.getByTestId("branch-repositories-card").element(),
      ...ACTION_BUTTONS.map((name) =>
        component.getByRole("button", { name, exact: true }).element()
      ),
      component.getByTestId("branch-tasks-card").element(),
    ]);
  });

  test.each<[string, RepositoriesState, TasksState]>([
    ["loaded", { data: buildBranchRepositoriesScenario("all-clear") }, LOADED_TASKS],
    ["loading", { data: undefined, isPending: true }, { data: undefined, isPending: true }],
    ["failed", { data: undefined }, { data: undefined }],
  ])(
    "passes exactly { branch } to the merge button when repositories and tasks are %s",
    async (_, repositories, tasks) => {
      // GIVEN
      const branch = setup({ isDefault: false, repositories, tasks });

      // WHEN
      const component = await renderDetails();

      // THEN
      await expect.element(component.getByRole("button", { name: "Merge" })).toBeVisible();
      expect(vi.mocked(BranchMergeButton)).toHaveBeenCalled();
      for (const [props] of vi.mocked(BranchMergeButton).mock.calls) {
        expect(props).toStrictEqual({ branch });
      }
    }
  );

  test("names related repositories in the Tasks card from the repositories query", async () => {
    // GIVEN
    setup({
      isDefault: false,
      tasks: {
        data: {
          count: 1,
          tasks: [
            {
              id: "task-1",
              title: "Import repository",
              branch: "ple-branch",
              state: "COMPLETED",
              workflow: "git-repository-import-object",
              relatedNodes: [{ id: "repo-2", kind: "CoreRepository" }],
              updatedAt: "2026-09-01T10:00:00Z",
            },
          ],
        },
      },
    });

    // WHEN
    const component = await renderDetails();

    // THEN
    const tasksCard = component.getByTestId("branch-tasks-card");
    await expect.element(tasksCard.getByText("infrastructure-templates")).toBeVisible();
    expect(vi.mocked(useGetBranchRepositories)).toHaveBeenCalledWith({
      branchName: "feature",
      syncWithGit: expect.any(Boolean),
    });
  });

  test("on the default branch, renders only the Details card", async () => {
    // GIVEN
    setup({ isDefault: true });

    // WHEN
    const component = await renderDetails();

    // THEN
    await expect.element(component.getByText("Details", { exact: true })).toBeVisible();
    await expect.element(component.getByTestId("branch-repositories-card")).not.toBeInTheDocument();
    await expect.element(component.getByTestId("branch-tasks-card")).not.toBeInTheDocument();
    for (const name of ACTION_BUTTONS) {
      await expect
        .element(component.getByRole("button", { name, exact: true }))
        .not.toBeInTheDocument();
    }
    expect(vi.mocked(useGetBranchRepositories)).not.toHaveBeenCalled();
    expect(vi.mocked(useGetBranchTasks)).not.toHaveBeenCalled();
  });
});
