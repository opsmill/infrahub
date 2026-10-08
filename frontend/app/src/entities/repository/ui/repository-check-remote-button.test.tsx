import { type QueryClient, useQueryClient } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { userEvent } from "vitest/browser";

import { formatWithPreferences } from "@/shared/context/date-preferences-context";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { checkRemoteRefsFromApi } from "@/entities/repository/api/check-remote-refs-from-api";
import { getRemoteCheckTaskFromApi } from "@/entities/repository/api/get-remote-check-task-from-api";
import { getRepositoryCommitsFromApi } from "@/entities/repository/api/get-repository-commits-from-api";
import { repositoriesQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";
import type { RepositoryRemoteCheck } from "@/entities/repository/ui/repository-check-remote-button";

import { render } from "../../../../tests/components/render";
import { initPointerTracking } from "../../../../tests/components/utils";
import { generateBranch } from "../../../../tests/fake/branch";
import { generatePermission } from "../../../../tests/fake/permission";
import {
  generateCommitsApiResult,
  generateReadOnlyCommitsResponse,
  READ_ONLY_CHECKED_AT,
} from "../../../../tests/fake/repository-commit";
import {
  EARLIER_CHECKED_AT,
  generateCheckRemoteRefsApiResult,
  generateRemoteCheck,
  generateRemoteCheckTaskApiResult,
} from "../../../../tests/fake/repository-refs-check";
import { RepositoryCommitsManager } from "./repository-commits-manager";

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

const formatDateTime = (date: string) =>
  formatWithPreferences(date, { pattern: null, timezone: null }, "datetime");

let queryClient: QueryClient;

function CaptureQueryClient() {
  queryClient = useQueryClient();
  return null;
}

const commitLog = (remoteCheck: RepositoryRemoteCheck | null) => (
  <>
    <CaptureQueryClient />
    <div className="h-96">
      <RepositoryCommitsManager
        repositoryId={REPOSITORY_ID}
        repositoryLocation={null}
        remoteCheck={remoteCheck}
      />
    </div>
  </>
);

const renderCommitLog = (remoteCheck: RepositoryRemoteCheck | null = generateRemoteCheck()) =>
  render(commitLog(remoteCheck));

const useBranch = (name: string) =>
  vi.mocked(useCurrentBranch).mockReturnValue({
    currentBranch: generateBranch({ name }),
    setCurrentBranch: () => {},
  });

const pollCheckTaskAgain = () =>
  queryClient.invalidateQueries({
    queryKey: repositoriesQueryKeys.remoteCheckTask({ taskId: TASK_ID }),
  });

describe("Check remote now in the commit log", () => {
  beforeEach(() => {
    useBranch("test-branch");
    commitsApiMock.mockResolvedValue(generateCommitsApiResult(generateReadOnlyCommitsResponse()));
    checkRemoteRefsApiMock.mockResolvedValue(generateCheckRemoteRefsApiResult(TASK_ID));
    remoteCheckTaskApiMock.mockResolvedValue(generateRemoteCheckTaskApiResult({ isOngoing: true }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetAllMocks();
  });

  test("is offered on a read-only repository", async () => {
    // GIVEN
    const remoteCheck = generateRemoteCheck();

    // WHEN
    const component = await renderCommitLog(remoteCheck);

    // THEN
    await expect.element(component.getByRole("button", CHECK_BUTTON)).toBeEnabled();
  });

  test("is not offered on a read-write repository", async () => {
    // GIVEN
    const remoteCheck = null;

    // WHEN
    const component = await renderCommitLog(remoteCheck);

    // THEN
    await expect.element(component.getByRole("button", { name: "Refresh data" })).toBeVisible();
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

  test("explains why it is disabled without permission to update the repository", async () => {
    // GIVEN
    const component = await renderCommitLog(
      generateRemoteCheck({ updatePermission: generatePermission({ update: false }).update })
    );
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
    const component = await renderCommitLog(
      generateRemoteCheck({ updatePermission: generatePermission({ update: false }).update })
    );
    const checkButton = component.getByRole("button", CHECK_BUTTON);
    await expect.element(checkButton).toBeVisible();

    // WHEN
    checkButton.element().focus();
    await userEvent.keyboard("{Enter}");

    // THEN
    await expect.element(checkButton).toHaveFocus();
    // A press that got through would call the API on a later tick, so give it one before asserting.
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(checkRemoteRefsApiMock).not.toHaveBeenCalled();
  });

  test("starts a check on the current branch and links its task in the repository", async () => {
    // GIVEN
    const component = await renderCommitLog();
    const checkButton = component.getByRole("button", CHECK_BUTTON);
    await expect.element(checkButton).toBeEnabled();

    // WHEN
    await checkButton.click();

    // THEN
    await expect
      .element(component.getByRole("link", { name: "View task" }))
      .toHaveAttribute(
        "href",
        expect.stringContaining(`/objects/CoreReadOnlyRepository/${REPOSITORY_ID}/tasks/${TASK_ID}`)
      );
    await expect.element(checkButton).toBeDisabled();
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
    await expect.element(component.getByRole("link", { name: "View task" })).toBeVisible();
    await component.rerender(<CaptureQueryClient />);

    // WHEN
    await component.rerender(commitLog(generateRemoteCheck()));

    // THEN
    await expect.element(component.getByRole("link", { name: "View task" })).toBeVisible();
    await expect.element(component.getByRole("button", CHECK_BUTTON)).toBeDisabled();
    expect(checkRemoteRefsApiMock).toHaveBeenCalledTimes(1);
  });

  test("does not show a check started on another branch", async () => {
    // GIVEN
    const component = await renderCommitLog();
    await component.getByRole("button", CHECK_BUTTON).click();
    await expect.element(component.getByRole("link", { name: "View task" })).toBeVisible();
    useBranch("other-branch");

    // WHEN
    await component.rerender(commitLog(generateRemoteCheck()));

    // THEN
    await expect.element(component.getByRole("button", CHECK_BUTTON)).toBeEnabled();
    expect(component.getByRole("link", { name: "View task" }).query()).toBeNull();
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
    await expect.element(component.getByRole("link", { name: "View task" })).toBeVisible();
    commitsApiMock.mockResolvedValue(generateCommitsApiResult(generateReadOnlyCommitsResponse()));
    remoteCheckTaskApiMock.mockResolvedValue(
      generateRemoteCheckTaskApiResult({ isOngoing: false })
    );

    // WHEN
    await pollCheckTaskAgain();

    // THEN
    await expect
      .element(component.getByText(`Checked ${formatDateTime(READ_ONLY_CHECKED_AT)}`))
      .toBeVisible();
    await expect.element(component.getByRole("button", CHECK_BUTTON)).toBeEnabled();
    expect(component.getByRole("link", { name: "View task" }).query()).toBeNull();
  });

  test("reloads the commit log after a check that ended before the first poll", async () => {
    // GIVEN
    commitsApiMock.mockResolvedValue(
      generateCommitsApiResult({
        ...generateReadOnlyCommitsResponse(),
        checked_at: EARLIER_CHECKED_AT,
      })
    );
    remoteCheckTaskApiMock.mockResolvedValue(
      generateRemoteCheckTaskApiResult({ isOngoing: false })
    );
    const component = await renderCommitLog();
    const checkButton = component.getByRole("button", CHECK_BUTTON);
    await expect.element(checkButton).toBeEnabled();
    commitsApiMock.mockResolvedValue(generateCommitsApiResult(generateReadOnlyCommitsResponse()));

    // WHEN
    await checkButton.click();

    // THEN
    await expect
      .element(component.getByText(`Checked ${formatDateTime(READ_ONLY_CHECKED_AT)}`))
      .toBeVisible();
    await expect.element(checkButton).toBeEnabled();
  });

  test("keeps the check running when one poll fails", async () => {
    // GIVEN
    const component = await renderCommitLog();
    await component.getByRole("button", CHECK_BUTTON).click();
    await expect.element(component.getByRole("link", { name: "View task" })).toBeVisible();
    remoteCheckTaskApiMock.mockRejectedValue(new Error("Task manager unavailable"));

    // WHEN
    await pollCheckTaskAgain();

    // THEN
    await expect.element(component.getByRole("button", CHECK_BUTTON)).toBeDisabled();
    await expect.element(component.getByRole("link", { name: "View task" })).toBeVisible();
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
