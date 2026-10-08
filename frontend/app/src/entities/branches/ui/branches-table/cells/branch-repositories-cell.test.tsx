import { describe, expect, test } from "vitest";

import type {
  BranchGitStatus,
  BranchRepositoryState,
  UnloadedRepository,
} from "@/entities/branch-git-status/domain/model/branch-git-status";
import type { BranchTableRow } from "@/entities/branches/ui/branches-table/branch-table-row";
import { BranchRepositoriesCell } from "@/entities/branches/ui/branches-table/cells/branch-repositories-cell";

import { render } from "../../../../../../tests/components/render";
import { initPointerTracking } from "../../../../../../tests/components/utils";
import { generateBranch } from "../../../../../../tests/fake/branch";
import { generateBranchGitRepository } from "../../../../../../tests/fake/branch-git-status";
import { SYNC_STATUS } from "../../../../../../tests/fake/branch-repositories";

const FAILING_COMMIT = "1234567890abcdef1234567890abcdef12345678";
const LOAD_ERROR_MESSAGE = "Repository query timed out";

const repositoryState = (
  name: string,
  overrides: Partial<BranchRepositoryState> = {}
): BranchRepositoryState => ({
  repository: generateBranchGitRepository({ id: `repo-${name}`, name }),
  commit: "8f3c2a1",
  syncStatus: SYNC_STATUS.inSync,
  ...overrides,
});

const okStatus = (
  repositories: BranchRepositoryState[],
  unloaded: UnloadedRepository[] = []
): BranchGitStatus => ({ status: "ok", repositories, counts: [], unloaded });

const THREE_REPOSITORIES = okStatus([
  repositoryState("beta-repo", { syncStatus: SYNC_STATUS.importError, commit: FAILING_COMMIT }),
  repositoryState("alpha-repo"),
  repositoryState("gamma-repo"),
]);

const BROKEN_REPOSITORY: UnloadedRepository = {
  status: "error",
  repository: generateBranchGitRepository({ id: "repo-broken", name: "broken" }),
  message: "Repository index unavailable",
};

const renderCell = (gitStatus: BranchGitStatus, branchOverrides = {}) => {
  const branch: BranchTableRow = {
    ...generateBranch({ id: "branch-feature", name: "feature", sync_with_git: true }),
    ...branchOverrides,
    gitStatus,
  };
  return render(<BranchRepositoriesCell branch={branch} />);
};

describe("BranchRepositoriesCell", () => {
  test("shows the worst repository first, linked on the row's branch", async () => {
    // WHEN
    const component = await renderCell(THREE_REPOSITORIES);

    // THEN
    const link = component.getByRole("link", { name: "beta-repo" });
    await expect.element(link).toBeVisible();
    const href = new URL(link.element().getAttribute("href") ?? "", window.location.origin);
    expect(href.pathname).toContain("repo-beta-repo");
    expect(href.searchParams.get("branch")).toBe("feature");
    expect(component.getByRole("link", { name: "alpha-repo" }).query()).toBeNull();
  });

  test("shows the Git state label and the short commit in the repository pill's tooltip", async () => {
    // GIVEN
    const component = await renderCell(THREE_REPOSITORIES);
    await initPointerTracking(component.locator);

    // WHEN
    await component.getByRole("link", { name: "beta-repo" }).hover();

    // THEN
    await expect
      .element(component.getByRole("tooltip", { name: "Import Error · 1234567" }))
      .toBeVisible();
  });

  test("marks a read-only repository with no commit as read-only in the tooltip", async () => {
    // GIVEN
    const component = await renderCell(
      okStatus([
        repositoryState("golden-configs", {
          commit: null,
          repository: generateBranchGitRepository({
            name: "golden-configs",
            kind: "CoreReadOnlyRepository",
          }),
        }),
      ])
    );
    await initPointerTracking(component.locator);

    // WHEN
    await component.getByRole("link", { name: "golden-configs" }).hover();

    // THEN
    await expect
      .element(component.getByRole("tooltip", { name: "In Sync · read-only" }))
      .toBeVisible();
  });

  test("links the other repositories to the branch details page, naming the branch", async () => {
    // WHEN
    const component = await renderCell(THREE_REPOSITORIES);

    // THEN
    const more = component.getByRole("link", { name: "+2 more repositories on feature" });
    await expect.element(more).toHaveTextContent("+2 more");
    expect(more.element().getAttribute("href")).toBe("/branches/feature");
  });

  test("offers no link to other repositories for a single repository", async () => {
    // WHEN
    const component = await renderCell(okStatus([repositoryState("solo")]));

    // THEN
    await expect.element(component.getByRole("link", { name: "solo" })).toBeVisible();
    expect(component.getByRole("link", { name: /more/ }).query()).toBeNull();
  });

  test.each([
    { name: "the repository list is loading", gitStatus: { status: "pending" } },
    {
      name: "nothing is loaded yet",
      gitStatus: okStatus([], [{ status: "pending", repository: generateBranchGitRepository() }]),
    },
  ] satisfies Array<{ name: string; gitStatus: BranchGitStatus }>)(
    "shows a silent spinner while $name",
    async ({ gitStatus }) => {
      // WHEN
      const component = await renderCell(gitStatus);

      // THEN
      await expect.element(component.getByText("Loading repositories")).toBeInTheDocument();
      expect(component.getByRole("status").query()).toBeNull();
    }
  );

  test("shows the loaded repositories while another one is still loading", async () => {
    // WHEN
    const component = await renderCell(
      okStatus(
        [repositoryState("fast")],
        [{ status: "pending", repository: generateBranchGitRepository({ name: "slow" }) }]
      )
    );

    // THEN
    await expect.element(component.getByRole("link", { name: "fast" })).toBeVisible();
    expect(component.getByText("Loading repositories").query()).toBeNull();
  });

  test.each([
    {
      name: "a branch not synced with Git has no repositories",
      gitStatus: okStatus([]),
      branch: { sync_with_git: false },
      text: "Not synced with Git",
    },
    {
      name: "a synced branch has no repositories",
      gitStatus: okStatus([]),
      branch: { sync_with_git: true },
      text: "No repositories",
    },
    {
      name: "the account may not view them",
      gitStatus: { status: "denied" },
      text: "No permission",
    },
    {
      name: "they could not be loaded",
      gitStatus: { status: "error", message: LOAD_ERROR_MESSAGE },
      text: "Could not load repositories",
      cellText: `Could not load repositories${LOAD_ERROR_MESSAGE}`,
    },
  ] satisfies Array<{
    name: string;
    gitStatus: BranchGitStatus;
    branch?: object;
    text: string;
    cellText?: string;
  }>)("reads $text when $name", async ({ gitStatus, branch = {}, text, cellText = text }) => {
    // WHEN
    const component = await renderCell(gitStatus, branch);

    // THEN
    await expect.element(component.getByText(text, { exact: true })).toBeVisible();
    await expect
      .element(component.getByTestId("branch-repositories-cell-feature"))
      .toHaveTextContent(cellText);
  });

  test("shows the load error's message on hover and to assistive technology", async () => {
    // GIVEN
    const component = await renderCell({ status: "error", message: LOAD_ERROR_MESSAGE });
    await initPointerTracking(component.locator);

    // WHEN
    await component.getByText("Could not load repositories", { exact: true }).hover();

    // THEN
    await expect
      .element(component.getByRole("tooltip", { name: LOAD_ERROR_MESSAGE }))
      .toBeVisible();
    await expect
      .element(
        component
          .getByTestId("branch-repositories-cell-feature")
          .getByText(LOAD_ERROR_MESSAGE, { exact: true })
      )
      .toHaveClass("sr-only");
  });

  test("shows the loaded repositories with a notice naming the one that could not be loaded", async () => {
    // GIVEN
    const reason = "broken: Repository index unavailable";
    const component = await renderCell(okStatus([repositoryState("visible")], [BROKEN_REPOSITORY]));
    await initPointerTracking(component.locator);

    // WHEN
    await component.getByText("1 repository could not be loaded", { exact: true }).hover();

    // THEN
    await expect.element(component.getByRole("link", { name: "visible" })).toBeVisible();
    await expect.element(component.getByRole("tooltip", { name: reason })).toBeVisible();
    await expect
      .element(
        component.getByTestId("branch-repositories-cell-feature").getByText(reason, { exact: true })
      )
      .toHaveClass("sr-only");
  });

  test("shows only the notice when no repository loaded for the branch", async () => {
    // WHEN
    const component = await renderCell(
      okStatus(
        [],
        [
          BROKEN_REPOSITORY,
          { status: "denied", repository: generateBranchGitRepository({ name: "secrets" }) },
        ]
      )
    );

    // THEN
    await expect
      .element(component.getByText("2 repositories could not be loaded", { exact: true }))
      .toBeVisible();
    await expect
      .element(component.getByTestId("branch-repositories-cell-feature"))
      .toHaveTextContent(
        "2 repositories could not be loadedbroken: Repository index unavailable · secrets: No permission"
      );
  });
});
