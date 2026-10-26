import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { cleanup } from "vitest-browser-react";

import type { Branch } from "@/shared/api/graphql/generated/types";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { getBranchActionState } from "@/entities/branches/domain/use-cases/get-branch-action-state";
import { rebaseBranch } from "@/entities/branches/domain/use-cases/rebase-branch";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { useDefaultBranch } from "@/entities/branches/ui/hooks/use-default-branch";
import type { PermissionDecision } from "@/entities/permission/domain/model/permission";
import { hasGlobalPermission } from "@/entities/permission/domain/use-cases/has-global-permission";
import {
  READONLY_REPOSITORY_KIND,
  REPOSITORY_KIND,
  type RepositoryCommitLog,
  RepositoryGitCondition,
} from "@/entities/repository/domain/model/repository";
import { getLatestRepositoryImportTask } from "@/entities/repository/domain/use-cases/get-latest-repository-import-task";
import { reimportLastCommit } from "@/entities/repository/domain/use-cases/reimport-last-commit";
import { isTaskFinished } from "@/entities/tasks/domain/use-cases/is-task-finished";

import { render } from "../../../../tests/components/render";
import { initPointerTracking } from "../../../../tests/components/utils";
import { generateBranch } from "../../../../tests/fake/branch";
import { RepositoryCommitsHeader } from "./repository-commits-header";

vi.mock("@/entities/authentication/ui/auth-provider");
vi.mock("@/entities/branches/ui/branches-provider");
vi.mock("@/entities/branches/ui/hooks/use-default-branch");
vi.mock("@/entities/branches/domain/use-cases/get-branch-action-state");
vi.mock("@/entities/branches/domain/use-cases/rebase-branch");
vi.mock("@/entities/permission/domain/use-cases/has-global-permission");
vi.mock("@/entities/repository/domain/use-cases/get-latest-repository-import-task");
vi.mock("@/entities/repository/domain/use-cases/reimport-last-commit");
vi.mock("@/entities/tasks/domain/use-cases/is-task-finished");

const BRANCH_NAME = "feature-1";
const DEFAULT_BRANCH_NAME = "trunk";
const REBASE_TASK_ID = "rebase-task-1";
const IMPORT_TASK_ID = "import-task-1";

const behindLog: RepositoryCommitLog = {
  repository_id: "repo-1",
  branch_name: BRANCH_NAME,
  git_ref: "main",
  condition: RepositoryGitCondition.BEHIND,
  imported_commit: "a".repeat(40),
  remote_head: "b".repeat(40),
  pending_count: 2,
  fetched_at: null,
  checked_at: null,
  unavailable: null,
  commits: [],
};

const renderHeader = ({
  kind = REPOSITORY_KIND,
  rebaseOnly = true,
  updatePermission = { isAllowed: true },
}: {
  kind?: string;
  rebaseOnly?: boolean;
  updatePermission?: PermissionDecision;
} = {}) =>
  render(
    <RepositoryCommitsHeader
      commitLog={{ kind: "loaded", log: behindLog }}
      rebaseOnly={rebaseOnly}
      repository={{
        id: "repo-1",
        name: "infrahub-demo",
        isReadOnly: kind === READONLY_REPOSITORY_KIND,
        isStaging: false,
        updatePermission,
      }}
    />
  );

describe("RepositoryCommitsHeader", () => {
  beforeEach(() => {
    vi.mocked(useCurrentBranch).mockReturnValue({
      currentBranch: generateBranch({ name: BRANCH_NAME, sync_with_git: false }),
      setCurrentBranch: () => {},
    });
    vi.mocked(useDefaultBranch).mockReturnValue(
      generateBranch({ name: DEFAULT_BRANCH_NAME, is_default: true })
    );
    vi.mocked(useAuth).mockReturnValue({
      accessToken: "token",
      isAuthenticated: true,
      setToken: () => {},
      user: { id: "user-1" },
    } as ReturnType<typeof useAuth>);
    vi.mocked(hasGlobalPermission).mockResolvedValue(true);
    vi.mocked(getBranchActionState).mockResolvedValue({ ongoingTaskCount: 0 });
    vi.mocked(getLatestRepositoryImportTask).mockResolvedValue({ status: "none" });
    vi.mocked(isTaskFinished).mockResolvedValue(false);
    vi.mocked(rebaseBranch).mockResolvedValue({
      branch: { name: BRANCH_NAME } as Branch,
      relatedTaskId: REBASE_TASK_ID,
    });
    vi.mocked(reimportLastCommit).mockResolvedValue({ ok: true, taskId: IMPORT_TASK_ID });
  });

  afterEach(async () => {
    // Unmounted first, or a background poll re-renders the tab against reset mocks.
    await cleanup();
    vi.resetAllMocks();
  });

  test("asks to confirm the rebase of the whole branch onto the default branch", async () => {
    // GIVEN
    const component = await renderHeader();

    // WHEN
    await component.getByRole("button", { name: "Rebase branch" }).click();

    // THEN
    const dialog = component.getByRole("dialog");
    await expect
      .element(dialog.getByRole("heading", { name: "Rebase the whole branch?" }))
      .toBeVisible();
    await expect
      .element(dialog)
      .toMatchTextContent(new RegExp(`${BRANCH_NAME} is rebased on ${DEFAULT_BRANCH_NAME}\\.`));
    await expect
      .element(dialog.getByText("all its data and all its repositories, not only infrahub-demo"))
      .toBeVisible();
    expect(rebaseBranch).not.toHaveBeenCalled();
  });

  test("rebases the current branch once confirmed and shows the running rebase", async () => {
    // GIVEN
    const component = await renderHeader();
    await component.getByRole("button", { name: "Rebase branch" }).click();

    // WHEN
    await component.getByRole("dialog").getByRole("button", { name: "Rebase branch" }).click();

    // THEN
    await expect.element(component.getByRole("heading", { name: "Rebase running" })).toBeVisible();
    await expect.element(component.getByRole("dialog")).not.toBeInTheDocument();
    expect(rebaseBranch).toHaveBeenCalledWith(
      { branchName: BRANCH_NAME, waitUntilCompletion: false },
      expect.anything()
    );
    await expect
      .element(component.getByText(`is being rebased on ${DEFAULT_BRANCH_NAME},`, { exact: false }))
      .toBeVisible();
  });

  test("does not rebase when the confirmation is cancelled", async () => {
    // GIVEN
    const component = await renderHeader();
    await component.getByRole("button", { name: "Rebase branch" }).click();

    // WHEN
    await component.getByRole("dialog").getByRole("button", { name: "Cancel" }).click();

    // THEN
    await expect.element(component.getByRole("dialog")).not.toBeInTheDocument();
    expect(rebaseBranch).not.toHaveBeenCalled();
  });

  test("disables Rebase branch and describes it with the missing rebase permission", async () => {
    // GIVEN
    vi.mocked(hasGlobalPermission).mockResolvedValue(false);

    // WHEN
    const component = await renderHeader();

    // THEN
    await expect
      .element(component.getByText("You need permission to rebase branches."))
      .toBeVisible();
    const rebaseButton = component.getByRole("button", { name: "Rebase branch" });
    await expect.element(rebaseButton).toBeDisabled();
    await expect
      .element(rebaseButton)
      .toHaveAccessibleDescription("You need permission to rebase branches.");
    await rebaseButton.click({ force: true });
    expect(component.getByRole("dialog").query()).toBeNull();
  });

  test("disables Rebase branch without a reason while the rebase permission loads", async () => {
    // GIVEN
    vi.mocked(hasGlobalPermission).mockReturnValue(new Promise(() => {}));

    // WHEN
    const component = await renderHeader();

    // THEN
    await expect.element(component.getByRole("button", { name: "Rebase branch" })).toBeDisabled();
    expect(component.getByText(/You need permission/).query()).toBeNull();
  });

  test("disables the read-only repository actions with the reason of the permission decision", async () => {
    // GIVEN
    const updatePermission: PermissionDecision = {
      isAllowed: false,
      message: "Ask an administrator for access.",
    };
    const component = await renderHeader({
      kind: READONLY_REPOSITORY_KIND,
      rebaseOnly: false,
      updatePermission,
    });
    await initPointerTracking(component.locator);

    // WHEN
    await component.getByRole("button", { name: "Import latest commit" }).hover();

    // THEN
    await expect
      .element(component.getByRole("tooltip", { name: "Ask an administrator for access." }))
      .toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Import latest commit" }))
      .toBeDisabled();
    await expect
      .element(component.getByRole("button", { name: "Check remote now" }))
      .toBeDisabled();
  });

  test("asks a signed-out user on the default branch to sign in", async () => {
    // GIVEN
    vi.mocked(useCurrentBranch).mockReturnValue({
      currentBranch: generateBranch({ name: "main", is_default: true }),
      setCurrentBranch: () => {},
    });
    vi.mocked(useAuth).mockReturnValue({
      accessToken: null,
      isAuthenticated: false,
      setToken: () => {},
    } as unknown as ReturnType<typeof useAuth>);

    // WHEN
    const component = await renderHeader({ kind: READONLY_REPOSITORY_KIND, rebaseOnly: false });

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Import latest commit" }))
      .toHaveAccessibleDescription("Sign in to change this repository.");
    expect(
      component.getByText("You need permission to edit the default branch.").query()
    ).toBeNull();
    await expect
      .element(component.getByRole("button", { name: "Import latest commit" }))
      .toBeDisabled();
  });

  test("imports the latest commit on the current branch and shows the running import", async () => {
    // GIVEN
    const component = await renderHeader({ kind: READONLY_REPOSITORY_KIND, rebaseOnly: false });

    // WHEN
    await component.getByRole("button", { name: "Import latest commit" }).click();

    // THEN
    await expect.element(component.getByRole("heading", { name: "Import running" })).toBeVisible();
    expect(reimportLastCommit).toHaveBeenCalledWith({
      repositoryId: "repo-1",
      branchName: BRANCH_NAME,
    });
  });

  test("shows the tracked ref before the remote was ever checked", async () => {
    // WHEN
    const component = await renderHeader();

    // THEN
    await expect.element(component.getByText("Tracking main")).toBeVisible();
  });
});
