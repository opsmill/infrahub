import { type QueryClient, useQueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, test, vi } from "vitest";

import { queryClient as appQueryClient } from "@/shared/api/rest/client";
import { formatWithPreferences } from "@/shared/context/date-preferences-context";

import type { PermissionDecision } from "@/entities/permission/domain/model/permission";
import { checkRemoteRefsFromApi } from "@/entities/repository/api/check-remote-refs-from-api";
import { getRepositoryCommitStatusFromApi } from "@/entities/repository/api/get-repository-commit-status-from-api";
import { getRepositoryCommitsFromApi } from "@/entities/repository/api/get-repository-commits-from-api";
import { getRepositoryCommitsQueryOptions } from "@/entities/repository/ui/queries/get-repository-commits.query";
import { checkTaskDetailsFromApi } from "@/entities/tasks/api/check-task-details-from-api";

import { render } from "../../../../tests/components/render";
import { generateBranch } from "../../../../tests/fake/branch";
import {
  generateBehindCommitsResponse,
  generateInSyncCommitsResponse,
  generateNotClonedCommitsResponse,
  generateReadOnlyCommitsResponse,
  READ_ONLY_CHECKED_AT,
  READ_ONLY_FETCHED_AT,
  type RepositoryCommitsWire,
} from "../../../../tests/fake/repository-commit";
import { RepositoryCommitsManager } from "./repository-commits-manager";
import { RepositoryCommitsTab } from "./repository-commits-tab";

vi.mock("@/entities/repository/api/get-repository-commit-status-from-api");
vi.mock("@/entities/repository/api/get-repository-commits-from-api");
vi.mock("@/entities/repository/api/check-remote-refs-from-api");
vi.mock("@/entities/tasks/api/check-task-details-from-api");

const apiMock = vi.mocked(getRepositoryCommitStatusFromApi);
const commitsApiMock = vi.mocked(getRepositoryCommitsFromApi);
const checkRemoteRefsApiMock = vi.mocked(checkRemoteRefsFromApi);
const taskDetailsApiMock = vi.mocked(checkTaskDetailsFromApi);

type ApiResult = Awaited<ReturnType<typeof getRepositoryCommitStatusFromApi>>;

const apiResult = ({ condition, pending_count, unavailable }: RepositoryCommitsWire) =>
  ({
    data: {
      InfrahubRepositoryCommits: {
        condition,
        pending_count,
        unavailable: unavailable && { reason: unavailable.reason },
      },
    },
  }) as ApiResult;

type CommitsApiResult = Awaited<ReturnType<typeof getRepositoryCommitsFromApi>>;

const commitsApiResult = (response: RepositoryCommitsWire) =>
  ({ data: { InfrahubRepositoryCommits: response } }) as unknown as CommitsApiResult;

let queryClient: QueryClient;

function CaptureQueryClient() {
  queryClient = useQueryClient();
  return null;
}

const renderTab = () =>
  render(
    <>
      <CaptureQueryClient />
      <RepositoryCommitsTab objectKind="CoreRepository" objectId="repo-1" />
    </>
  );

const COMMITS_TAB_PATH = "/objects/CoreRepository/repo-1/repository_commits";

interface CommitLogRepository {
  isReadOnly?: boolean;
  updatePermission?: PermissionDecision;
}

const renderTabWithCommitLog = ({
  isReadOnly = false,
  updatePermission = { isAllowed: true },
}: CommitLogRepository = {}) => {
  window.history.pushState({}, "", COMMITS_TAB_PATH);
  return render(
    <>
      <CaptureQueryClient />
      <RepositoryCommitsTab objectKind="CoreRepository" objectId="repo-1" />
      <RepositoryCommitsManager
        repositoryId="repo-1"
        repositoryLocation="/remote/repo"
        isReadOnly={isReadOnly}
        updatePermission={updatePermission}
      />
    </>
  );
};

type CheckRemoteRefsApiResult = Awaited<ReturnType<typeof checkRemoteRefsFromApi>>;

const checkRemoteRefsApiResult = (taskId: string) =>
  ({
    data: { InfrahubReadOnlyRepositoryCheckRefs: { ok: true, task: { id: taskId } } },
  }) as CheckRemoteRefsApiResult;

type TaskDetailsApiResult = Awaited<ReturnType<typeof checkTaskDetailsFromApi>>;

const ongoingTaskCount = (count: number) =>
  ({ data: { InfrahubTask: { count } } }) as TaskDetailsApiResult;

const formatDateTime = (date: string) =>
  formatWithPreferences(date, { pattern: null, timezone: null }, "datetime");

const CHECK_TASK_ID = "check-task-1";

describe("RepositoryCommitsTab", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetAllMocks();
    window.history.pushState({}, "", "/");
  });

  test("shows the pending-import count when the branch is behind", async () => {
    // GIVEN
    apiMock.mockResolvedValue(apiResult(generateBehindCommitsResponse()));

    // WHEN
    const component = await renderTab();

    // THEN
    expect(apiMock).toHaveBeenCalledWith(expect.objectContaining({ repositoryId: "repo-1" }));
    const tab = component.getByRole("link", { name: "Commits 2 pending import" });
    await expect.element(tab).toBeVisible();
    await expect.element(tab.getByText("2")).toBeVisible();
  });

  test("shows 0 when the branch is in sync", async () => {
    // GIVEN
    apiMock.mockResolvedValue(apiResult(generateInSyncCommitsResponse()));

    // WHEN
    const component = await renderTab();

    // THEN
    await expect
      .element(component.getByRole("link", { name: "Commits 0 pending import" }))
      .toBeVisible();
  });

  test("shows no count when no worker holds a copy", async () => {
    // GIVEN
    apiMock.mockResolvedValue(apiResult(generateNotClonedCommitsResponse()));

    // WHEN
    const component = await renderTab();

    // THEN
    await expect
      .element(component.getByRole("link", { name: "Commits", exact: true }))
      .toBeVisible();
    expect(component.getByText(/pending import/).query()).toBeNull();
    expect(component.getByText(/^\d+$/).query()).toBeNull();
  });

  test("follows the status the commit log brings in", async () => {
    // GIVEN
    apiMock.mockResolvedValue(apiResult(generateInSyncCommitsResponse()));
    commitsApiMock.mockResolvedValue(commitsApiResult(generateBehindCommitsResponse()));
    const component = await renderTab();
    await expect
      .element(component.getByRole("link", { name: "Commits 0 pending import" }))
      .toBeVisible();

    // WHEN
    await queryClient.fetchInfiniteQuery(
      getRepositoryCommitsQueryOptions({
        repositoryId: "repo-1",
        branchName: generateBranch().name,
      })
    );

    // THEN
    await expect
      .element(component.getByRole("link", { name: "Commits 2 pending import" }))
      .toBeVisible();
    expect(apiMock).toHaveBeenCalledTimes(1);
  });

  test("reads the status from the commit log while it is on screen", async () => {
    // GIVEN
    commitsApiMock.mockResolvedValue(commitsApiResult(generateBehindCommitsResponse()));

    // WHEN
    const component = await renderTabWithCommitLog();

    // THEN
    await expect
      .element(component.getByRole("link", { name: "Commits 2 pending import" }))
      .toBeVisible();
    expect(apiMock).not.toHaveBeenCalled();
  });

  test("refreshing the open Commits tab makes no separate status read", async () => {
    // GIVEN
    commitsApiMock.mockResolvedValue(commitsApiResult(generateBehindCommitsResponse()));
    const component = await renderTabWithCommitLog();
    await expect
      .element(component.getByRole("link", { name: "Commits 2 pending import" }))
      .toBeVisible();

    vi.spyOn(appQueryClient, "invalidateQueries").mockImplementation((filters) =>
      queryClient.invalidateQueries(filters)
    );

    // WHEN
    await component.getByRole("button", { name: "Refresh data" }).click();

    // THEN
    await expect.poll(() => commitsApiMock.mock.calls.length).toBe(2);
    expect(apiMock).not.toHaveBeenCalled();
  });

  test("reads the status itself when the commit log failed to load", async () => {
    // GIVEN
    commitsApiMock.mockRejectedValue(new Error("No worker answered"));
    apiMock.mockResolvedValue(apiResult(generateBehindCommitsResponse()));

    // WHEN
    const component = await renderTabWithCommitLog();

    // THEN
    await expect
      .element(component.getByRole("link", { name: "Commits 2 pending import" }))
      .toBeVisible();
    expect(apiMock).toHaveBeenCalledTimes(1);
  });
});

describe("Check remote now", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetAllMocks();
    window.history.pushState({}, "", "/");
  });

  test("is offered on a read-only repository", async () => {
    // GIVEN
    commitsApiMock.mockResolvedValue(commitsApiResult(generateReadOnlyCommitsResponse()));

    // WHEN
    const component = await renderTabWithCommitLog({ isReadOnly: true });

    // THEN
    await expect.element(component.getByRole("button", { name: "Check remote now" })).toBeEnabled();
  });

  test("is not offered on a read-write repository", async () => {
    // GIVEN
    commitsApiMock.mockResolvedValue(commitsApiResult(generateBehindCommitsResponse()));

    // WHEN
    const component = await renderTabWithCommitLog();

    // THEN
    await expect.element(component.getByRole("button", { name: "Refresh data" })).toBeVisible();
    expect(component.getByRole("button", { name: "Check remote now" }).query()).toBeNull();
  });

  test("is disabled without permission to update the repository", async () => {
    // GIVEN
    commitsApiMock.mockResolvedValue(commitsApiResult(generateReadOnlyCommitsResponse()));

    // WHEN
    const component = await renderTabWithCommitLog({
      isReadOnly: true,
      updatePermission: { isAllowed: false, message: "You do not have permission to update" },
    });

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Check remote now" }))
      .toBeDisabled();
  });

  test("links the running check's task and stays disabled until it ends", async () => {
    // GIVEN
    commitsApiMock.mockResolvedValue(commitsApiResult(generateReadOnlyCommitsResponse()));
    checkRemoteRefsApiMock.mockResolvedValue(checkRemoteRefsApiResult(CHECK_TASK_ID));
    taskDetailsApiMock.mockResolvedValue(ongoingTaskCount(1));
    const component = await renderTabWithCommitLog({ isReadOnly: true });
    const checkButton = component.getByRole("button", { name: "Check remote now" });

    // WHEN
    await checkButton.click();

    // THEN
    await expect
      .element(component.getByRole("link", { name: "View task" }))
      .toHaveAttribute("href", expect.stringContaining(`/tasks/${CHECK_TASK_ID}`));
    await expect.element(checkButton).toBeDisabled();
    expect(checkRemoteRefsApiMock).toHaveBeenCalledTimes(1);
    expect(checkRemoteRefsApiMock).toHaveBeenCalledWith(
      expect.objectContaining({ repositoryId: "repo-1" })
    );
    expect(taskDetailsApiMock).toHaveBeenCalledWith(
      expect.objectContaining({ ids: [CHECK_TASK_ID] })
    );
  });

  test("shows the new check time above the older update time once the check ends", async () => {
    // GIVEN
    const checkedBefore = "2025-03-10T18:00:00Z";
    commitsApiMock.mockResolvedValue(
      commitsApiResult({ ...generateReadOnlyCommitsResponse(), checked_at: checkedBefore })
    );
    checkRemoteRefsApiMock.mockResolvedValue(checkRemoteRefsApiResult(CHECK_TASK_ID));
    taskDetailsApiMock.mockResolvedValue(ongoingTaskCount(0));
    const component = await renderTabWithCommitLog({ isReadOnly: true });
    await expect
      .element(component.getByText(`Checked ${formatDateTime(checkedBefore)}`))
      .toBeVisible();
    commitsApiMock.mockResolvedValue(commitsApiResult(generateReadOnlyCommitsResponse()));

    // WHEN
    await component.getByRole("button", { name: "Check remote now" }).click();

    // THEN
    await expect
      .element(component.getByText(`Checked ${formatDateTime(READ_ONLY_CHECKED_AT)}`))
      .toBeVisible();
    await expect
      .element(component.getByText(`Updated ${formatDateTime(READ_ONLY_FETCHED_AT)}`))
      .toBeVisible();
    await expect.element(component.getByRole("button", { name: "Check remote now" })).toBeEnabled();
    expect(component.getByRole("link", { name: "View task" }).query()).toBeNull();
  });
});
