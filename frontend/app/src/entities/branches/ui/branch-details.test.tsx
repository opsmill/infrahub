import { describe, expect, test, vi } from "vitest";

import { BranchMergeButton } from "@/entities/branches/ui/branch-merge-button";
import { useGetBranchDetails } from "@/entities/branches/ui/queries/get-branch-details.query";
import type { BranchRepositoriesResult } from "@/entities/repository/domain/model/branch-repository";
import { useGetBranchRepositories } from "@/entities/repository/ui/queries/get-branch-repositories.query";
import { useGetRepositoryImportError } from "@/entities/repository/ui/queries/get-repository-import-error.query";

import { render } from "../../../../tests/components/render";
import { generateBranch } from "../../../../tests/fake/branch";
import { buildBranchRepositoriesScenario } from "../../../../tests/fake/branch-repositories";
import { BranchDetails } from "./branch-details";

vi.mock("@/entities/branches/ui/queries/get-branch-details.query");
vi.mock("@/entities/repository/ui/queries/get-branch-repositories.query");
vi.mock("@/entities/repository/ui/queries/get-repository-import-error.query");
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

const setup = ({
  isDefault,
  repositories = { data: buildBranchRepositoriesScenario("all-clear") },
}: {
  isDefault: boolean;
  repositories?: RepositoriesState;
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
  test("on a non-default branch, renders Details, then Git repositories, then the action buttons", async () => {
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
    ]);
  });

  test.each<[string, RepositoriesState]>([
    ["loaded", { data: buildBranchRepositoriesScenario("all-clear") }],
    ["loading", { data: undefined, isPending: true }],
    ["failed", { data: undefined }],
  ])(
    "passes exactly { branch } to the merge button when repositories are %s",
    async (_, repositories) => {
      // GIVEN
      const branch = setup({ isDefault: false, repositories });

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

  test("on the default branch, renders only the Details card", async () => {
    // GIVEN
    setup({ isDefault: true });

    // WHEN
    const component = await renderDetails();

    // THEN
    await expect.element(component.getByText("Details", { exact: true })).toBeVisible();
    await expect.element(component.getByTestId("branch-repositories-card")).not.toBeInTheDocument();
    for (const name of ACTION_BUTTONS) {
      await expect
        .element(component.getByRole("button", { name, exact: true }))
        .not.toBeInTheDocument();
    }
    expect(vi.mocked(useGetBranchRepositories)).not.toHaveBeenCalled();
  });
});
