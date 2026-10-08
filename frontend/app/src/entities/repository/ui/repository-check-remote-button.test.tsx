import { type QueryClient, useQueryClient } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { userEvent } from "vitest/browser";

import { formatWithPreferences } from "@/shared/context/date-preferences-context";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { checkRemoteRefsFromApi } from "@/entities/repository/api/check-remote-refs-from-api";
import { getRepositoryCommitsFromApi } from "@/entities/repository/api/get-repository-commits-from-api";
import { getRunningRefsCheckFromApi } from "@/entities/repository/api/get-running-refs-check-from-api";
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
  generateCheckRemoteRefsApiResult,
  generateRemoteCheck,
  generateRunningRefsCheckApiResult,
} from "../../../../tests/fake/repository-refs-check";
import { RepositoryCommitsManager } from "./repository-commits-manager";

vi.mock("@/entities/branches/ui/branches-provider");
vi.mock("@/entities/repository/api/get-repository-commits-from-api");
vi.mock("@/entities/repository/api/check-remote-refs-from-api");
vi.mock("@/entities/repository/api/get-running-refs-check-from-api");

const commitsApiMock = vi.mocked(getRepositoryCommitsFromApi);
const checkRemoteRefsApiMock = vi.mocked(checkRemoteRefsFromApi);
const runningRefsCheckApiMock = vi.mocked(getRunningRefsCheckFromApi);

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

const renderCommitLog = (remoteCheck: RepositoryRemoteCheck | null = generateRemoteCheck()) =>
  render(
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

const pollRunningCheckAgain = () =>
  queryClient.invalidateQueries({
    queryKey: repositoriesQueryKeys.runningRefsCheck({ repositoryId: REPOSITORY_ID }),
  });

describe("RepositoryCheckRemoteButton", () => {
  beforeEach(() => {
    vi.mocked(useCurrentBranch).mockReturnValue({
      currentBranch: generateBranch({ name: "test-branch" }),
      setCurrentBranch: () => {},
    });
    commitsApiMock.mockResolvedValue(generateCommitsApiResult(generateReadOnlyCommitsResponse()));
    runningRefsCheckApiMock.mockResolvedValue(generateRunningRefsCheckApiResult(null));
  });

  afterEach(() => {
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
    const component = await renderCommitLog(null);

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
    expect(checkRemoteRefsApiMock).not.toHaveBeenCalled();
  });

  test("shows a check started elsewhere and links its task in the repository", async () => {
    // GIVEN
    runningRefsCheckApiMock.mockResolvedValue(generateRunningRefsCheckApiResult(TASK_ID));

    // WHEN
    const component = await renderCommitLog();

    // THEN
    await expect
      .element(component.getByRole("link", { name: "View task" }))
      .toHaveAttribute(
        "href",
        expect.stringContaining(`/objects/CoreReadOnlyRepository/${REPOSITORY_ID}/tasks/${TASK_ID}`)
      );
    await expect.element(component.getByRole("button", CHECK_BUTTON)).toBeDisabled();
    expect(runningRefsCheckApiMock).toHaveBeenCalledWith(
      expect.objectContaining({ repositoryId: REPOSITORY_ID })
    );
  });

  test("starts a check on the current branch and follows it", async () => {
    // GIVEN
    checkRemoteRefsApiMock.mockResolvedValue(generateCheckRemoteRefsApiResult(TASK_ID));
    const component = await renderCommitLog();
    const checkButton = component.getByRole("button", CHECK_BUTTON);
    await expect.element(checkButton).toBeEnabled();
    runningRefsCheckApiMock.mockResolvedValue(generateRunningRefsCheckApiResult(TASK_ID));

    // WHEN
    await checkButton.click();

    // THEN
    await expect.element(component.getByRole("link", { name: "View task" })).toBeVisible();
    await expect.element(checkButton).toBeDisabled();
    expect(checkRemoteRefsApiMock).toHaveBeenCalledTimes(1);
    expect(checkRemoteRefsApiMock).toHaveBeenCalledWith({
      repositoryId: REPOSITORY_ID,
      branchName: "test-branch",
    });
  });

  test("reloads the commit log when the running check ends", async () => {
    // GIVEN
    const checkedBefore = "2025-03-10T18:00:00Z";
    commitsApiMock.mockResolvedValue(
      generateCommitsApiResult({ ...generateReadOnlyCommitsResponse(), checked_at: checkedBefore })
    );
    runningRefsCheckApiMock.mockResolvedValue(generateRunningRefsCheckApiResult(TASK_ID));
    const component = await renderCommitLog();
    await expect.element(component.getByRole("link", { name: "View task" })).toBeVisible();
    commitsApiMock.mockResolvedValue(generateCommitsApiResult(generateReadOnlyCommitsResponse()));
    runningRefsCheckApiMock.mockResolvedValue(generateRunningRefsCheckApiResult(null));

    // WHEN
    await pollRunningCheckAgain();

    // THEN
    await expect
      .element(component.getByText(`Checked ${formatDateTime(READ_ONLY_CHECKED_AT)}`))
      .toBeVisible();
    await expect.element(component.getByRole("button", CHECK_BUTTON)).toBeEnabled();
    expect(component.getByRole("link", { name: "View task" }).query()).toBeNull();
  });

  test("reloads the commit log after a check that ended before the next poll", async () => {
    // GIVEN
    commitsApiMock.mockResolvedValue(
      generateCommitsApiResult({
        ...generateReadOnlyCommitsResponse(),
        checked_at: "2025-03-10T18:00:00Z",
      })
    );
    checkRemoteRefsApiMock.mockResolvedValue(generateCheckRemoteRefsApiResult(TASK_ID));
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

  test("reloads the commit log when a check ended while the tab was closed", async () => {
    // GIVEN
    commitsApiMock.mockResolvedValue(
      generateCommitsApiResult({
        ...generateReadOnlyCommitsResponse(),
        checked_at: "2025-03-10T18:00:00Z",
      })
    );
    runningRefsCheckApiMock.mockResolvedValue(generateRunningRefsCheckApiResult(TASK_ID));
    const component = await renderCommitLog();
    await expect.element(component.getByRole("link", { name: "View task" })).toBeVisible();
    await component.rerender(<CaptureQueryClient />);
    commitsApiMock.mockResolvedValue(generateCommitsApiResult(generateReadOnlyCommitsResponse()));
    runningRefsCheckApiMock.mockResolvedValue(generateRunningRefsCheckApiResult(null));

    // WHEN
    await component.rerender(
      <div className="h-96">
        <RepositoryCommitsManager
          repositoryId={REPOSITORY_ID}
          repositoryLocation={null}
          remoteCheck={generateRemoteCheck()}
        />
      </div>
    );

    // THEN
    await expect
      .element(component.getByText(`Checked ${formatDateTime(READ_ONLY_CHECKED_AT)}`))
      .toBeVisible();
    await expect.element(component.getByRole("button", CHECK_BUTTON)).toBeEnabled();
  });

  test("keeps the check running when one poll fails", async () => {
    // GIVEN
    runningRefsCheckApiMock.mockResolvedValue(generateRunningRefsCheckApiResult(TASK_ID));
    const component = await renderCommitLog();
    await expect.element(component.getByRole("link", { name: "View task" })).toBeVisible();
    runningRefsCheckApiMock.mockRejectedValue(new Error("Task manager unavailable"));

    // WHEN
    await pollRunningCheckAgain();

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
  });
});
