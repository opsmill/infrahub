import { describe, expect, test, vi } from "vitest";

import { BranchMergeButton } from "@/entities/branches/ui/branch-merge-button";
import { useGetBranchDetails } from "@/entities/branches/ui/queries/get-branch-details.query";
import { BranchRepositoriesCard } from "@/entities/repository/ui/branch-repositories/branch-repositories-card";
import { BranchTasksCard } from "@/entities/tasks/ui/branch-tasks/branch-tasks-card";

import { render } from "../../../../tests/components/render";
import { generateBranch } from "../../../../tests/fake/branch";
import { BranchDetails } from "./branch-details";

vi.mock("@/entities/branches/ui/queries/get-branch-details.query");
vi.mock("@/entities/repository/ui/branch-repositories/branch-repositories-card", () => ({
  BranchRepositoriesCard: vi.fn(() => <section data-testid="branch-repositories-card" />),
}));
vi.mock("@/entities/tasks/ui/branch-tasks/branch-tasks-card", () => ({
  BranchTasksCard: vi.fn(() => <section data-testid="branch-tasks-card" />),
}));
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

const setup = ({
  isDefault,
  syncWithGit = true,
}: {
  isDefault: boolean;
  syncWithGit?: boolean;
}) => {
  vi.clearAllMocks();
  const branch = generateBranch({
    name: "feature",
    is_default: isDefault,
    sync_with_git: syncWithGit,
  });
  vi.mocked(useGetBranchDetails).mockReturnValue({
    isPending: false,
    error: null,
    data: branch,
  } as unknown as ReturnType<typeof useGetBranchDetails>);
  return branch;
};

const renderDetails = () => render(<BranchDetails branchName="feature" />);

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
    expectInDocumentOrder([
      component.getByText("Details", { exact: true }).element(),
      component.getByTestId("branch-repositories-card").element(),
      ...ACTION_BUTTONS.map((name) =>
        component.getByRole("button", { name, exact: true }).element()
      ),
      component.getByTestId("branch-tasks-card").element(),
    ]);
  });

  test("gives each card the branch it shows and nothing else", async () => {
    // GIVEN
    setup({ isDefault: false, syncWithGit: false });

    // WHEN
    const component = await renderDetails();

    // THEN
    await expect.element(component.getByTestId("branch-tasks-card")).toBeInTheDocument();
    expect(vi.mocked(BranchRepositoriesCard).mock.lastCall?.[0]).toStrictEqual({
      branchName: "feature",
      syncWithGit: false,
    });
    expect(vi.mocked(BranchTasksCard).mock.lastCall?.[0]).toStrictEqual({ branchName: "feature" });
  });

  test("passes exactly { branch } to the merge button", async () => {
    // GIVEN
    const branch = setup({ isDefault: false });

    // WHEN
    const component = await renderDetails();

    // THEN
    await expect.element(component.getByRole("button", { name: "Merge" })).toBeVisible();
    for (const [props] of vi.mocked(BranchMergeButton).mock.calls) {
      expect(props).toStrictEqual({ branch });
    }
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
    expect(vi.mocked(BranchRepositoriesCard)).not.toHaveBeenCalled();
    expect(vi.mocked(BranchTasksCard)).not.toHaveBeenCalled();
  });
});
