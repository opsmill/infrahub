import { type QueryClient, useQueryClient } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { userEvent } from "vitest/browser";
import { cleanup } from "vitest-browser-react";

import { formatWithPreferences } from "@/shared/context/date-preferences-context";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type { PermissionDecision } from "@/entities/permission/domain/model/permission";
import { checkRemoteRefsFromApi } from "@/entities/repository/api/check-remote-refs-from-api";
import { getRemoteCheckTaskFromApi } from "@/entities/repository/api/get-remote-check-task-from-api";
import { getRepositoryCommitsFromApi } from "@/entities/repository/api/get-repository-commits-from-api";
import {
  READONLY_REPOSITORY_KIND,
  REPOSITORY_INTERNAL_STATUS_STAGING,
  REPOSITORY_KIND,
} from "@/entities/repository/domain/model/repository";
import { CHECK_REMOTE_REFS_MUTATION_KEY } from "@/entities/repository/ui/queries/check-remote-refs.mutation";
import { repositoriesQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

import { render } from "../../../../tests/components/render";
import { initPointerTracking } from "../../../../tests/components/utils";
import { generateBranch } from "../../../../tests/fake/branch";
import { generatePermission } from "../../../../tests/fake/permission";
import {
  generateCommitsApiResult,
  generateReadOnlyCommitsResponse,
  generateRepositoryCommitsResponse,
  READ_ONLY_CHECKED_AT,
} from "../../../../tests/fake/repository-commit";
import {
  EARLIER_CHECKED_AT,
  generateCheckRemoteRefsApiResult,
  generateRemoteCheckTaskApiResult,
} from "../../../../tests/fake/repository-refs-check";
import { RepositoryCommitsManager } from "./repository-commits-manager";

vi.mock("@/entities/authentication/ui/auth-provider");
vi.mock("@/entities/branches/ui/branches-provider");
vi.mock("@/entities/repository/api/get-repository-commits-from-api");
vi.mock("@/entities/repository/api/check-remote-refs-from-api");
vi.mock("@/entities/repository/api/get-remote-check-task-from-api");

const commitsApiMock = vi.mocked(getRepositoryCommitsFromApi);
const checkRemoteRefsApiMock = vi.mocked(checkRemoteRefsFromApi);
const remoteCheckTaskApiMock = vi.mocked(getRemoteCheckTaskFromApi);

const REPOSITORY_ID = "repo-1";
const TASK_ID = "check-task-1";
const CHECK_BUTTON = { name: "Check remote now" };
const RUNNING_CHECK_BUTTON = { name: "Check running" };

const formatDate = (date: string) =>
  formatWithPreferences(date, { pattern: null, timezone: null }, "date");

let queryClient: QueryClient;

function CaptureQueryClient() {
  queryClient = useQueryClient();
  return null;
}

interface CommitLogOptions {
  isReadOnly?: boolean;
  isStaging?: boolean;
  updatePermission?: PermissionDecision;
}

const commitLog = ({
  isReadOnly = true,
  isStaging = false,
  updatePermission = generatePermission().update,
}: CommitLogOptions = {}) => (
  <>
    <CaptureQueryClient />
    <div className="h-96">
      <RepositoryCommitsManager
        repositoryId={REPOSITORY_ID}
        repositoryKind={isReadOnly ? READONLY_REPOSITORY_KIND : REPOSITORY_KIND}
        repositoryName="infrahub-demo"
        isReadOnly={isReadOnly}
        repositoryInternalStatus={isStaging ? REPOSITORY_INTERNAL_STATUS_STAGING : "active"}
        repositoryLocation={null}
        updatePermission={updatePermission}
      />
    </div>
  </>
);

const renderCommitLog = (options?: CommitLogOptions) => render(commitLog(options));

const WITHOUT_UPDATE_PERMISSION = {
  updatePermission: generatePermission({ update: false }).update,
};

const useBranch = (name: string) =>
  vi.mocked(useCurrentBranch).mockReturnValue({
    currentBranch: generateBranch({ name, sync_with_git: true }),
    setCurrentBranch: () => {},
  });

const pollCheckTaskAgain = () =>
  queryClient.invalidateQueries({
    queryKey: repositoriesQueryKeys.remoteCheckTask({ taskId: TASK_ID }),
  });

describe("Check remote now in the commit log", () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue({
      accessToken: "token",
      isAuthenticated: true,
      setToken: () => {},
      user: { id: "user-1" },
    } as ReturnType<typeof useAuth>);
    useBranch("test-branch");
    commitsApiMock.mockResolvedValue(generateCommitsApiResult(generateReadOnlyCommitsResponse()));
    checkRemoteRefsApiMock.mockResolvedValue(generateCheckRemoteRefsApiResult(TASK_ID));
    remoteCheckTaskApiMock.mockResolvedValue(generateRemoteCheckTaskApiResult("RUNNING"));
  });

  afterEach(async () => {
    // Unmounted first, or a background poll re-renders the tab against reset mocks.
    await cleanup();
    vi.restoreAllMocks();
    vi.resetAllMocks();
  });

  test("is offered on a read-only repository", async () => {
    // WHEN
    const component = await renderCommitLog();

    // THEN
    await expect.element(component.getByRole("button", CHECK_BUTTON)).toBeEnabled();
  });

  test("is not offered on a read-write repository", async () => {
    // WHEN
    const component = await renderCommitLog({ isReadOnly: false });

    // THEN
    await expect
      .element(component.getByRole("heading", { name: "1 commit pending import" }))
      .toBeVisible();
    expect(component.getByRole("button", CHECK_BUTTON).query()).toBeNull();
  });

  test("is offered when the commit log failed to load", async () => {
    // GIVEN
    commitsApiMock.mockRejectedValue(new Error("No worker answered"));

    // WHEN
    const component = await renderCommitLog();

    // THEN
    await expect.element(component.getByText("No worker answered")).toBeVisible();
    await expect.element(component.getByRole("button", CHECK_BUTTON)).toBeEnabled();
  });

  test("is offered beside Import latest commit when no commit was imported yet", async () => {
    // GIVEN
    commitsApiMock.mockResolvedValue(
      generateCommitsApiResult(generateRepositoryCommitsResponse({ condition: "NOT_TRACKED" }))
    );

    // WHEN
    const component = await renderCommitLog();

    // THEN
    await expect
      .element(component.getByRole("heading", { name: "No commit imported yet" }))
      .toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Import latest commit" }))
      .toBeEnabled();
    await expect.element(component.getByRole("button", CHECK_BUTTON)).toBeEnabled();
  });

  test("is not offered for a read-only repository added on the branch", async () => {
    // WHEN
    const component = await renderCommitLog({ isStaging: true });

    // THEN
    await expect
      .element(component.getByRole("heading", { name: "1 commit pending import" }))
      .toBeVisible();
    expect(component.getByRole("button", CHECK_BUTTON).query()).toBeNull();
  });

  test("is not offered for a read-only repository added on the branch when the commit log failed to load", async () => {
    // GIVEN
    commitsApiMock.mockRejectedValue(new Error("No worker answered"));

    // WHEN
    const component = await renderCommitLog({ isStaging: true });

    // THEN
    await expect.element(component.getByText("No worker answered")).toBeVisible();
    expect(component.getByRole("button", CHECK_BUTTON).query()).toBeNull();
  });

  test("explains why it is disabled with the reason of the update permission decision", async () => {
    // GIVEN
    const component = await renderCommitLog(WITHOUT_UPDATE_PERMISSION);
    const checkButton = component.getByRole("button", CHECK_BUTTON);
    await expect.element(checkButton).toBeVisible();

    // WHEN
    await initPointerTracking(component.locator);
    await checkButton.hover();

    // THEN
    await expect
      .element(component.getByRole("tooltip", { name: "Update not allowed" }))
      .toBeVisible();
    await expect.element(checkButton).toBeDisabled();
    // Move the pointer off the trigger so the tooltip does not carry into the next test.
    await initPointerTracking(component.locator);
  });

  test("does not start a check when pressed without permission", async () => {
    // GIVEN
    const component = await renderCommitLog(WITHOUT_UPDATE_PERMISSION);
    const checkButton = component.getByRole("button", CHECK_BUTTON);
    await expect.element(checkButton).toBeVisible();

    // WHEN
    checkButton.element().focus();
    await userEvent.keyboard("{Enter}");

    // THEN
    await expect.element(checkButton).toHaveFocus();
    // A press that got through adds the mutation synchronously, before the API is called.
    expect(
      queryClient.getMutationCache().findAll({ mutationKey: CHECK_REMOTE_REFS_MUTATION_KEY })
    ).toHaveLength(0);
    expect(checkRemoteRefsApiMock).not.toHaveBeenCalled();
  });

  test("starts a check on the current branch and shows it running", async () => {
    // GIVEN
    const component = await renderCommitLog();
    const checkButton = component.getByRole("button", CHECK_BUTTON);
    await expect.element(checkButton).toBeEnabled();

    // WHEN
    await checkButton.click();

    // THEN
    await expect.element(component.getByRole("button", RUNNING_CHECK_BUTTON)).toBeDisabled();
    expect(checkRemoteRefsApiMock).toHaveBeenCalledTimes(1);
    expect(checkRemoteRefsApiMock).toHaveBeenCalledWith({
      repositoryId: REPOSITORY_ID,
      branchName: "test-branch",
    });
    expect(remoteCheckTaskApiMock).toHaveBeenCalledWith(
      expect.objectContaining({ taskId: TASK_ID })
    );
  });

  test("follows a running check after the commit view remounts", async () => {
    // GIVEN
    const component = await renderCommitLog();
    await component.getByRole("button", CHECK_BUTTON).click();
    await expect.element(component.getByRole("button", RUNNING_CHECK_BUTTON)).toBeVisible();
    await component.rerender(<CaptureQueryClient />);

    // WHEN
    await component.rerender(commitLog());

    // THEN
    await expect.element(component.getByRole("button", RUNNING_CHECK_BUTTON)).toBeDisabled();
    expect(checkRemoteRefsApiMock).toHaveBeenCalledTimes(1);
  });

  test("does not show a check started on another branch", async () => {
    // GIVEN
    const component = await renderCommitLog();
    await component.getByRole("button", CHECK_BUTTON).click();
    await expect.element(component.getByRole("button", RUNNING_CHECK_BUTTON)).toBeVisible();
    useBranch("other-branch");

    // WHEN
    await component.rerender(commitLog());

    // THEN
    await expect.element(component.getByRole("button", CHECK_BUTTON)).toBeEnabled();
  });

  test("reloads the commit log when the check ends", async () => {
    // GIVEN
    commitsApiMock.mockResolvedValue(
      generateCommitsApiResult({
        ...generateReadOnlyCommitsResponse(),
        checked_at: EARLIER_CHECKED_AT,
      })
    );
    const component = await renderCommitLog();
    await component.getByRole("button", CHECK_BUTTON).click();
    await expect.element(component.getByRole("button", RUNNING_CHECK_BUTTON)).toBeVisible();
    commitsApiMock.mockResolvedValue(generateCommitsApiResult(generateReadOnlyCommitsResponse()));
    remoteCheckTaskApiMock.mockResolvedValue(generateRemoteCheckTaskApiResult("COMPLETED"));

    // WHEN
    await pollCheckTaskAgain();

    // THEN
    await expect
      .element(component.getByText(`Remote checked ${formatDate(READ_ONLY_CHECKED_AT)}`))
      .toBeVisible();
    await expect.element(component.getByRole("button", CHECK_BUTTON)).toBeEnabled();
  });

  test("reloads the commit log after a check that ended before the first poll", async () => {
    // GIVEN
    commitsApiMock.mockResolvedValue(
      generateCommitsApiResult({
        ...generateReadOnlyCommitsResponse(),
        checked_at: EARLIER_CHECKED_AT,
      })
    );
    remoteCheckTaskApiMock.mockResolvedValue(generateRemoteCheckTaskApiResult("COMPLETED"));
    const component = await renderCommitLog();
    const checkButton = component.getByRole("button", CHECK_BUTTON);
    await expect.element(checkButton).toBeEnabled();
    commitsApiMock.mockResolvedValue(generateCommitsApiResult(generateReadOnlyCommitsResponse()));

    // WHEN
    await checkButton.click();

    // THEN
    await expect
      .element(component.getByText(`Remote checked ${formatDate(READ_ONLY_CHECKED_AT)}`))
      .toBeVisible();
    await expect.element(checkButton).toBeEnabled();
  });

  test("stops following a started task the task manager no longer lists", async () => {
    // GIVEN
    commitsApiMock.mockResolvedValue(
      generateCommitsApiResult({
        ...generateReadOnlyCommitsResponse(),
        checked_at: EARLIER_CHECKED_AT,
      })
    );
    const component = await renderCommitLog();
    await component.getByRole("button", CHECK_BUTTON).click();
    await expect.element(component.getByRole("button", RUNNING_CHECK_BUTTON)).toBeVisible();
    commitsApiMock.mockResolvedValue(generateCommitsApiResult(generateReadOnlyCommitsResponse()));
    remoteCheckTaskApiMock.mockResolvedValue(generateRemoteCheckTaskApiResult(null));

    // WHEN
    await pollCheckTaskAgain();

    // THEN
    await expect.element(component.getByRole("button", CHECK_BUTTON)).toBeEnabled();
    await expect
      .element(component.getByText(`Remote checked ${formatDate(READ_ONLY_CHECKED_AT)}`))
      .toBeVisible();
  });

  test("keeps the check running when one poll fails", async () => {
    // GIVEN
    const component = await renderCommitLog();
    await component.getByRole("button", CHECK_BUTTON).click();
    await expect.element(component.getByRole("button", RUNNING_CHECK_BUTTON)).toBeVisible();
    remoteCheckTaskApiMock.mockRejectedValue(new Error("Task manager unavailable"));

    // WHEN
    await pollCheckTaskAgain();

    // THEN
    await expect.element(component.getByRole("button", RUNNING_CHECK_BUTTON)).toBeDisabled();
  });

  test("reports a check that could not start and stays available", async () => {
    // GIVEN
    checkRemoteRefsApiMock.mockRejectedValue(new Error("Repository is not active"));
    const component = await renderCommitLog();
    const checkButton = component.getByRole("button", CHECK_BUTTON);

    // WHEN
    await checkButton.click();

    // THEN
    await expect
      .element(component.getByText("Error checking the remote: Repository is not active"))
      .toBeVisible();
    await expect.element(checkButton).toBeEnabled();
    expect(remoteCheckTaskApiMock).not.toHaveBeenCalled();
  });
});
