import { describe, expect, test } from "vitest";

import type {
  BranchGitStatus,
  BranchRepositoryState,
} from "@/entities/branch-git-status/domain/model/branch-git-status";
import type { BranchTableRow } from "@/entities/branches/ui/branches-table/branch-table-row";
import { BranchGitStateCell } from "@/entities/branches/ui/branches-table/cells/branch-git-state-cell";

import { render } from "../../../../../../tests/components/render";
import { initPointerTracking } from "../../../../../../tests/components/utils";
import { generateBranch } from "../../../../../../tests/fake/branch";
import { generateBranchGitRepository } from "../../../../../../tests/fake/branch-git-status";
import { SYNC_STATUS } from "../../../../../../tests/fake/branch-repositories";

const repositoryState = (
  name: string,
  syncStatus: BranchRepositoryState["syncStatus"]
): BranchRepositoryState => ({
  repository: generateBranchGitRepository({ id: `repo-${name}`, name }),
  commit: "8f3c2a1",
  syncStatus,
});

const renderCell = (gitStatus: BranchGitStatus) => {
  const branch: BranchTableRow = {
    ...generateBranch({ id: "branch-feature", name: "feature" }),
    gitStatus,
  };
  return render(<BranchGitStateCell branch={branch} />);
};

describe("BranchGitStateCell", () => {
  test("shows the worst Git state with its share, and the count of each state", async () => {
    // GIVEN
    const component = await renderCell({
      status: "ok",
      repositories: [
        repositoryState("beta-repo", SYNC_STATUS.importError),
        repositoryState("alpha-repo", SYNC_STATUS.inSync),
        repositoryState("gamma-repo", SYNC_STATUS.inSync),
      ],
      counts: [
        { value: "error-import", label: "Import Error", count: 1 },
        { value: "in-sync", label: "In Sync", count: 2 },
      ],
      unloaded: [],
    });
    await initPointerTracking(component.locator);

    // WHEN
    await component.getByText("1/3", { exact: true }).hover();

    // THEN
    await expect.element(component.getByText("Import Error", { exact: true })).toBeVisible();
    await expect
      .element(component.getByRole("tooltip", { name: "Import Error: 1 · In Sync: 2" }))
      .toBeVisible();
    await expect
      .element(
        component
          .getByTestId("branch-git-state-cell-feature")
          .getByText("Import Error: 1 · In Sync: 2", { exact: true })
      )
      .toHaveClass("sr-only");
  });

  test("shows no share for a single repository", async () => {
    // WHEN
    const component = await renderCell({
      status: "ok",
      repositories: [repositoryState("solo", SYNC_STATUS.inSync)],
      counts: [{ value: "in-sync", label: "In Sync", count: 1 }],
      unloaded: [],
    });

    // THEN
    await expect
      .element(component.getByTestId("branch-git-state-cell-feature"))
      .toHaveTextContent(/^In Sync$/);
  });

  test.each([
    { name: "loading", gitStatus: { status: "pending" } },
    { name: "denied", gitStatus: { status: "denied" } },
    { name: "failed", gitStatus: { status: "error", message: "boom" } },
    {
      name: "without repositories",
      gitStatus: { status: "ok", repositories: [], counts: [], unloaded: [] },
    },
  ] satisfies Array<{ name: string; gitStatus: BranchGitStatus }>)(
    "is blank when $name",
    async ({ gitStatus }) => {
      // WHEN
      const component = await renderCell(gitStatus);

      // THEN
      await expect
        .element(component.getByTestId("branch-git-state-cell-feature"))
        .toBeEmptyDOMElement();
    }
  );
});
