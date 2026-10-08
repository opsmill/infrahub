import { InfiniteQueryObserver, type QueryClient, useQueryClient } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { queryClient as appQueryClient } from "@/shared/api/rest/client";
import { formatWithPreferences } from "@/shared/context/date-preferences-context";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type { PermissionDecision } from "@/entities/permission/domain/model/permission";
import { checkRemoteRefsFromApi } from "@/entities/repository/api/check-remote-refs-from-api";
import { getRepositoryCommitsFromApi } from "@/entities/repository/api/get-repository-commits-from-api";
import type { RepositoryGitCondition } from "@/entities/repository/domain/model/repository";
import { getRepositoryCommitsQueryOptions } from "@/entities/repository/ui/queries/get-repository-commits.query";
import {
  REPOSITORY_COMMITS_MAX_RETRIES,
  REPOSITORY_COMMITS_RETRY_DELAY_MS,
} from "@/entities/repository/ui/queries/repository-commits.constants";
import { checkTaskDetailsFromApi } from "@/entities/tasks/api/check-task-details-from-api";

import { render } from "../../../../tests/components/render";
import { generateBranch } from "../../../../tests/fake/branch";
import {
  BEHIND_HEAD,
  BEHIND_IMPORTED,
  generateBehindCommitsResponse,
  generateCommitsApiResult,
  generateFirstCommitsPage,
  generateInSyncCommitsResponse,
  generateJustCheckedCommitsResponse,
  generateNotClonedCommitsResponse,
  generateNotImplementedCommitsResponse,
  generateOrphanedCommitsResponse,
  generateReadOnlyCommitsResponse,
  generateRepositoryCommitsResponse,
  generateRewrittenCommitsResponse,
  generateSecondCommitsPage,
  IN_SYNC_HEAD,
  JUST_CHECKED_AT,
  NOT_CLONED_MESSAGE,
  NOT_IMPLEMENTED_MESSAGE,
  PAGE_ONE_HEAD,
  PAGE_ONE_LAST,
  PAGE_TWO_FIRST,
  READ_ONLY_CHECKED_AT,
  READ_ONLY_FETCHED_AT,
  type RepositoryCommitsWire,
} from "../../../../tests/fake/repository-commit";
import { RepositoryCommitsManager } from "./repository-commits-manager";

vi.mock("@/entities/branches/ui/branches-provider");
vi.mock("@/entities/repository/api/get-repository-commits-from-api");
vi.mock("@/entities/repository/api/check-remote-refs-from-api");
vi.mock("@/entities/tasks/api/check-task-details-from-api");

const apiMock = vi.mocked(getRepositoryCommitsFromApi);
const checkRemoteRefsApiMock = vi.mocked(checkRemoteRefsFromApi);
const taskDetailsApiMock = vi.mocked(checkTaskDetailsFromApi);
const useCurrentBranchMock = vi.mocked(useCurrentBranch);

type ApiResult = Awaited<ReturnType<typeof getRepositoryCommitsFromApi>>;

const formatDate = (date: string) =>
  formatWithPreferences(date, { pattern: null, timezone: null }, "date");
const formatDateTime = (date: string) =>
  formatWithPreferences(date, { pattern: null, timezone: null }, "datetime");

const STALE_NOTICE =
  "Couldn't refresh the commit log right now. Showing the last loaded commits; older commits load after a successful refresh.";

let queryClient: QueryClient;

function CaptureQueryClient() {
  queryClient = useQueryClient();
  return null;
}

interface TabRepository {
  isReadOnly?: boolean;
  updatePermission?: PermissionDecision;
}

const tab = ({
  isReadOnly = false,
  updatePermission = { isAllowed: true },
}: TabRepository = {}) => (
  <>
    <CaptureQueryClient />
    {/* Bounded like the tab panel, or the scroll sentinel can start in view and load page two on its own. */}
    <div className="h-96">
      <RepositoryCommitsManager
        repositoryId="repo-1"
        repositoryLocation="https://github.com/opsmill/infrahub-demo.git"
        isReadOnly={isReadOnly}
        updatePermission={updatePermission}
      />
    </div>
  </>
);

const renderTab = (repository?: TabRepository) => render(tab(repository));

const useBranch = (name: string) =>
  useCurrentBranchMock.mockReturnValue({
    currentBranch: generateBranch({ name }),
    setCurrentBranch: () => {},
  });

describe("RepositoryCommitsManager", () => {
  beforeEach(() => {
    useBranch("test-branch");
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.resetAllMocks();
  });

  test("renders every commit field newest-first as returned", async () => {
    // GIVEN
    apiMock.mockResolvedValue(generateCommitsApiResult(generateBehindCommitsResponse()));

    // WHEN
    const component = await renderTab();

    // THEN
    const rows = component.getByTestId("data-table-row");
    await expect.element(rows.nth(0).getByText(BEHIND_HEAD)).toBeVisible();
    await expect.element(rows.nth(0).getByText("Bump firmware baseline")).toBeVisible();
    await expect.element(rows.nth(0).getByText("Grace Hopper")).toBeVisible();
    await expect.element(rows.nth(0).getByText(formatDate("2025-03-10T10:00:00Z"))).toBeVisible();
    await expect.element(rows.nth(5).getByText("e5f6a7b")).toBeVisible();
    await expect.element(rows.nth(5).getByText("Initial import")).toBeVisible();
  });

  test("labels head, imported and pending rows from the response, not from their position", async () => {
    // GIVEN
    apiMock.mockResolvedValue(generateCommitsApiResult(generateBehindCommitsResponse()));

    // WHEN
    const component = await renderTab();

    // THEN
    const rows = component.getByTestId("data-table-row");
    await expect.element(rows.nth(0).getByText("Remote head")).toBeVisible();
    await expect.element(rows.nth(1).getByText("Pending import")).toBeVisible();
    expect(rows.nth(2).getByText("Pending import").query()).toBeNull();
    await expect.element(rows.nth(3).getByText("Pending import")).toBeVisible();
    await expect.element(rows.nth(4).getByText("Imported")).toBeVisible();
    await expect.element(component.getByText("2 commits pending import")).toBeVisible();
  });

  test("puts both markers on the same row when the remote head is the imported commit", async () => {
    // GIVEN
    apiMock.mockResolvedValue(generateCommitsApiResult(generateInSyncCommitsResponse()));

    // WHEN
    const component = await renderTab();

    // THEN
    const headRow = component.getByTestId("data-table-row").filter({ hasText: IN_SYNC_HEAD });
    await expect.element(headRow.getByText("Remote head")).toBeVisible();
    await expect.element(headRow.getByText("Imported")).toBeVisible();
    expect(component.getByText("Pending import").query()).toBeNull();
  });

  test("replaces the pending line with the rewritten notice", async () => {
    // GIVEN
    apiMock.mockResolvedValue(generateCommitsApiResult(generateRewrittenCommitsResponse()));

    // WHEN
    const component = await renderTab();

    // THEN
    await expect
      .element(component.getByRole("note").filter({ hasText: "The tracked ref was rewritten" }))
      .toBeVisible();
    expect(component.getByText(/pending import/i).query()).toBeNull();
    expect(component.getByText("Imported", { exact: true }).query()).toBeNull();
    const rows = component.getByTestId("data-table-row");
    await expect.element(rows.nth(1).getByText("Not on current history")).toBeVisible();
    await expect.element(rows.nth(2).getByText("Not on current history")).toBeVisible();
  });

  test.each<{ condition: RepositoryGitCondition; texts: string[] }>([
    {
      condition: "ORPHANED",
      texts: ["The imported commit could not be found on the remote."],
    },
    {
      condition: "NOT_TRACKED",
      texts: ["No commit log", "This branch tracks no remote ref."],
    },
    {
      condition: "NO_REMOTE",
      texts: ["No commit log", "The tracked ref has no remote counterpart."],
    },
    {
      condition: "UNAVAILABLE",
      texts: ["Commit log not available yet", "Waiting for a worker to answer."],
    },
  ])("explains the $condition condition", async ({ condition, texts }) => {
    // GIVEN
    const response =
      condition === "ORPHANED"
        ? generateOrphanedCommitsResponse()
        : generateRepositoryCommitsResponse({ condition, unavailable: null });
    apiMock.mockResolvedValue(generateCommitsApiResult(response));

    // WHEN
    const component = await renderTab();

    // THEN
    for (const text of texts) {
      await expect.element(component.getByText(text)).toBeVisible();
    }
  });

  test("keeps the tracked ref and the refresh button above the not-yet-available state", async () => {
    // GIVEN
    apiMock.mockResolvedValue(generateCommitsApiResult(generateNotClonedCommitsResponse()));

    // WHEN
    const component = await renderTab();

    // THEN
    await expect.element(component.getByText(NOT_CLONED_MESSAGE)).toBeVisible();
    await expect.element(component.getByText("Tracking main")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Refresh data" })).toBeVisible();
  });

  test("renders the not-yet-available message when no worker holds a copy", async () => {
    // GIVEN
    apiMock.mockResolvedValue(generateCommitsApiResult(generateNotClonedCommitsResponse()));

    // WHEN
    const component = await renderTab();

    // THEN
    await expect.element(component.getByText("Commit log not available yet")).toBeVisible();
    await expect.element(component.getByText(NOT_CLONED_MESSAGE)).toBeVisible();
    expect(component.getByText("Sorry, something went wrong.").query()).toBeNull();
  });

  test("renders a settled not-available message when reading commits is not implemented", async () => {
    // GIVEN
    apiMock.mockResolvedValue(generateCommitsApiResult(generateNotImplementedCommitsResponse()));

    // WHEN
    const component = await renderTab();

    // THEN
    await expect
      .element(component.getByText("Commit log not available", { exact: true }))
      .toBeVisible();
    await expect.element(component.getByText(NOT_IMPLEMENTED_MESSAGE)).toBeVisible();
    expect(component.getByText("Commit log not available yet").query()).toBeNull();
  });

  test.each<{ condition: RepositoryGitCondition; response: RepositoryCommitsWire }>([
    {
      condition: "NOT_TRACKED",
      response: generateRepositoryCommitsResponse({ condition: "NOT_TRACKED", git_ref: null }),
    },
    {
      condition: "NO_REMOTE",
      response: generateRepositoryCommitsResponse({ condition: "NO_REMOTE" }),
    },
  ])(
    "refetches the log when refresh is pressed on the $condition empty state",
    async ({ response }) => {
      // GIVEN
      apiMock
        .mockResolvedValueOnce(generateCommitsApiResult(response))
        .mockResolvedValue(generateCommitsApiResult(generateBehindCommitsResponse()));
      const component = await renderTab();
      await expect.element(component.getByRole("button", { name: "Refresh data" })).toBeVisible();
      vi.spyOn(appQueryClient, "invalidateQueries").mockImplementation((filters) =>
        queryClient.invalidateQueries(filters)
      );

      // WHEN
      await component.getByRole("button", { name: "Refresh data" }).click();

      // THEN
      await expect.element(component.getByText(BEHIND_HEAD)).toBeVisible();
      expect(apiMock).toHaveBeenCalledTimes(2);
    }
  );

  test("refreshes only the current repository's commit log", async () => {
    // GIVEN
    apiMock.mockResolvedValue(generateCommitsApiResult(generateBehindCommitsResponse()));
    const callsFor = (repositoryId: string) =>
      apiMock.mock.calls.filter(([params]) => params.repositoryId === repositoryId).length;
    const component = await renderTab();
    await expect.element(component.getByText(BEHIND_HEAD)).toBeVisible();
    const unsubscribeOtherLog = new InfiniteQueryObserver(
      queryClient,
      getRepositoryCommitsQueryOptions({ repositoryId: "repo-2", branchName: "test-branch" })
    ).subscribe(() => {});
    await expect.poll(() => callsFor("repo-2")).toBe(1);
    vi.spyOn(appQueryClient, "invalidateQueries").mockImplementation((filters) =>
      queryClient.invalidateQueries(filters)
    );

    // WHEN
    await component.getByRole("button", { name: "Refresh data" }).click();

    // THEN
    await expect.poll(() => callsFor("repo-1")).toBe(2);
    expect(callsFor("repo-2")).toBe(1);
    unsubscribeOtherLog();
  });

  test("renders an error screen, not the not-yet-available state, when the query fails", async () => {
    // GIVEN
    apiMock.mockRejectedValue(new Error("Worker did not answer in time"));

    // WHEN
    const component = await renderTab();

    // THEN
    await expect.element(component.getByText("Worker did not answer in time")).toBeVisible();
    expect(component.getByText("Commit log not available yet").query()).toBeNull();
  });

  test("renders the error screen with the message when the repository cannot be read", async () => {
    // GIVEN
    apiMock.mockRejectedValue(
      new Error("Unable to find the node repo-1 / CoreRepository in the database.")
    );

    // WHEN
    const component = await renderTab();

    // THEN
    await expect
      .element(
        component.getByText("Unable to find the node repo-1 / CoreRepository in the database.")
      )
      .toBeVisible();
    await expect.element(component.getByRole("button", { name: "Refresh data" })).toBeVisible();
    expect(component.getByText(/Commit log not available/).query()).toBeNull();
  });

  test("offers a refresh on the error screen when the first load fails", async () => {
    // GIVEN
    apiMock.mockRejectedValue(new Error("Worker did not answer in time"));

    // WHEN
    const component = await renderTab();

    // THEN
    await expect.element(component.getByText("Worker did not answer in time")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Refresh data" })).toBeVisible();
  });

  test("keeps the not-yet-available state on screen while it retries, then renders the rows", async () => {
    // GIVEN
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"], shouldAdvanceTime: true });
    let answerSecondAttempt: (result: ApiResult) => void = () => {};
    apiMock
      .mockResolvedValueOnce(generateCommitsApiResult(generateNotClonedCommitsResponse()))
      .mockReturnValueOnce(
        new Promise<ApiResult>((resolve) => {
          answerSecondAttempt = resolve;
        })
      )
      .mockResolvedValue(generateCommitsApiResult(generateBehindCommitsResponse()));
    const component = await renderTab();
    await expect.element(component.getByText("Commit log not available yet")).toBeVisible();

    // WHEN
    await vi.advanceTimersByTimeAsync(REPOSITORY_COMMITS_RETRY_DELAY_MS);

    // THEN
    expect(apiMock).toHaveBeenCalledTimes(2);
    await expect.element(component.getByText("Commit log not available yet")).toBeVisible();
    expect(component.getByText("Loading...", { exact: true }).query()).toBeNull();
    answerSecondAttempt(generateCommitsApiResult(generateNotClonedCommitsResponse()));
    await expect
      .poll(() => component.getByText("Commit log not available yet").query())
      .not.toBeNull();
    expect(component.getByText("Loading...", { exact: true }).query()).toBeNull();
    await vi.advanceTimersByTimeAsync(REPOSITORY_COMMITS_RETRY_DELAY_MS);
    await expect.element(component.getByText(BEHIND_HEAD)).toBeVisible();
    expect(apiMock).toHaveBeenCalledTimes(3);
    expect(component.getByText("Commit log not available yet").query()).toBeNull();
  });

  test("asks for a refresh once it stops retrying an unavailable answer", async () => {
    // GIVEN
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"], shouldAdvanceTime: true });
    apiMock.mockResolvedValue(generateCommitsApiResult(generateNotClonedCommitsResponse()));
    const component = await renderTab();
    await expect.element(component.getByText(NOT_CLONED_MESSAGE)).toBeVisible();

    // WHEN
    for (let retry = 1; retry <= REPOSITORY_COMMITS_MAX_RETRIES; retry++) {
      await vi.advanceTimersByTimeAsync(REPOSITORY_COMMITS_RETRY_DELAY_MS);
      await expect.poll(() => apiMock.mock.calls.length).toBe(retry + 1);
    }

    // THEN
    await expect
      .element(component.getByText(`${NOT_CLONED_MESSAGE} Refresh to check again.`))
      .toBeVisible();
    await expect.element(component.getByText("Commit log not available yet")).toBeVisible();
    await vi.advanceTimersByTimeAsync(REPOSITORY_COMMITS_RETRY_DELAY_MS);
    expect(apiMock).toHaveBeenCalledTimes(REPOSITORY_COMMITS_MAX_RETRIES + 1);
  });

  test.each([
    {
      name: "reading commits is not implemented",
      answer: () =>
        Promise.resolve(generateCommitsApiResult(generateNotImplementedCommitsResponse())),
      text: NOT_IMPLEMENTED_MESSAGE,
    },
    {
      name: "the read fails",
      answer: () => Promise.reject(new Error("Worker did not answer in time")),
      text: "Worker did not answer in time",
    },
  ])("asks once and does not retry when $name", async ({ answer, text }) => {
    // GIVEN
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"], shouldAdvanceTime: true });
    apiMock.mockImplementation(answer);

    // WHEN
    const component = await renderTab();
    await expect.element(component.getByText(text)).toBeVisible();
    await vi.advanceTimersByTimeAsync(REPOSITORY_COMMITS_RETRY_DELAY_MS * 3);

    // THEN
    expect(apiMock).toHaveBeenCalledTimes(1);
    await expect.element(component.getByText(text)).toBeVisible();
  });

  test("renders the error screen when a retry fails after an unavailable answer", async () => {
    // GIVEN
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"], shouldAdvanceTime: true });
    apiMock
      .mockResolvedValueOnce(generateCommitsApiResult(generateNotClonedCommitsResponse()))
      .mockRejectedValue(new Error("Worker did not answer in time"));
    const component = await renderTab();
    await expect.element(component.getByText("Commit log not available yet")).toBeVisible();

    // WHEN
    await vi.advanceTimersByTimeAsync(REPOSITORY_COMMITS_RETRY_DELAY_MS);

    // THEN
    await expect.element(component.getByText("Worker did not answer in time")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Refresh data" })).toBeVisible();
    expect(component.getByText("Commit log not available yet").query()).toBeNull();
  });

  test("keeps the loaded rows as stale while a refresh answering unavailable is retried, then refreshes them", async () => {
    // GIVEN
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"], shouldAdvanceTime: true });
    apiMock
      .mockResolvedValueOnce(generateCommitsApiResult(generateBehindCommitsResponse()))
      .mockResolvedValueOnce(generateCommitsApiResult(generateNotClonedCommitsResponse()))
      .mockResolvedValue(generateCommitsApiResult(generateInSyncCommitsResponse()));
    const component = await renderTab();
    await expect.element(component.getByText(BEHIND_HEAD)).toBeVisible();
    const staleNotice = component.getByText(STALE_NOTICE);
    expect(staleNotice.query()).toBeNull();

    // WHEN
    const refetch = queryClient.refetchQueries();

    // THEN
    await expect.element(staleNotice).toBeVisible();
    await expect.element(component.getByText(BEHIND_HEAD)).toBeVisible();
    await expect.element(component.getByText(BEHIND_IMPORTED)).toBeVisible();
    expect(component.getByText("Commit log not available yet").query()).toBeNull();
    expect(apiMock).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(REPOSITORY_COMMITS_RETRY_DELAY_MS);
    await refetch;
    await expect.element(component.getByText(IN_SYNC_HEAD)).toBeVisible();
    expect(apiMock).toHaveBeenCalledTimes(3);
    expect(staleNotice.query()).toBeNull();
    expect(component.getByText(BEHIND_HEAD).query()).toBeNull();
  });

  test("refetches the log when refresh is pressed on the error screen", async () => {
    // GIVEN
    apiMock
      .mockRejectedValueOnce(new Error("Worker did not answer in time"))
      .mockResolvedValue(generateCommitsApiResult(generateBehindCommitsResponse()));
    const component = await renderTab();
    await expect.element(component.getByText("Worker did not answer in time")).toBeVisible();
    vi.spyOn(appQueryClient, "invalidateQueries").mockImplementation((filters) =>
      queryClient.invalidateQueries(filters)
    );

    // WHEN
    await component.getByRole("button", { name: "Refresh data" }).click();

    // THEN
    await expect.element(component.getByText(BEHIND_HEAD)).toBeVisible();
    expect(apiMock).toHaveBeenCalledTimes(2);
  });

  test("keeps the loaded rows when a later refresh fails", async () => {
    // GIVEN
    apiMock
      .mockResolvedValueOnce(generateCommitsApiResult(generateBehindCommitsResponse()))
      .mockRejectedValue(new Error("boom"));
    const component = await renderTab();
    await expect.element(component.getByText(BEHIND_HEAD)).toBeVisible();

    // WHEN
    await queryClient.refetchQueries();

    // THEN
    expect(apiMock).toHaveBeenCalledTimes(2);
    await expect.element(component.getByText(BEHIND_HEAD)).toBeVisible();
    await expect.element(component.getByText(BEHIND_IMPORTED)).toBeVisible();
    expect(component.getByText("boom").query()).toBeNull();
  });

  test("says the rows are stale while a refresh fails, until one succeeds", async () => {
    // GIVEN
    apiMock
      .mockResolvedValueOnce(generateCommitsApiResult(generateBehindCommitsResponse()))
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValue(generateCommitsApiResult(generateBehindCommitsResponse()));
    const component = await renderTab();
    await expect.element(component.getByText(BEHIND_HEAD)).toBeVisible();
    const staleNotice = component.getByText(STALE_NOTICE);
    expect(staleNotice.query()).toBeNull();

    // WHEN
    await queryClient.refetchQueries();

    // THEN
    await expect.element(staleNotice).toBeVisible();
    await expect.element(component.getByText(BEHIND_HEAD)).toBeVisible();
    await queryClient.refetchQueries();
    await expect.poll(() => staleNotice.query()).toBeNull();
    await expect.element(component.getByText(BEHIND_HEAD)).toBeVisible();
  });

  test("hides the stale notice while a refresh runs after an older page failed", async () => {
    // GIVEN
    let answerRefresh: (result: ApiResult) => void = () => {};
    apiMock
      .mockResolvedValueOnce(generateCommitsApiResult(generateFirstCommitsPage()))
      .mockRejectedValueOnce(new Error("Worker did not answer in time"))
      .mockReturnValueOnce(
        new Promise<ApiResult>((resolve) => {
          answerRefresh = resolve;
        })
      )
      .mockResolvedValue(generateCommitsApiResult(generateSecondCommitsPage()));
    const component = await renderTab();
    await expect.element(component.getByText(PAGE_ONE_HEAD)).toBeVisible();
    await component.getByText(PAGE_ONE_LAST).element().scrollIntoView({ block: "end" });
    await expect.element(component.getByRole("button", { name: "Retry" })).toBeVisible();
    vi.spyOn(appQueryClient, "invalidateQueries").mockImplementation((filters) =>
      queryClient.invalidateQueries(filters)
    );
    const staleNotice = component.getByText(STALE_NOTICE);

    // WHEN
    await component.getByRole("button", { name: "Refresh data" }).click();

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Refresh data" }))
      .toHaveAttribute("aria-disabled", "true");
    expect(apiMock).toHaveBeenCalledTimes(3);
    expect(staleNotice.query()).toBeNull();
    answerRefresh(generateCommitsApiResult(generateFirstCommitsPage()));
    await expect
      .element(component.getByRole("button", { name: "Refresh data" }))
      .not.toHaveAttribute("aria-disabled", "true");
    await expect.element(component.getByText(PAGE_ONE_HEAD)).toBeVisible();
    expect(staleNotice.query()).toBeNull();
  });

  test("drops the previous branch's rows when the branch changes", async () => {
    // GIVEN
    useBranch("main");
    apiMock
      .mockResolvedValueOnce(generateCommitsApiResult(generateBehindCommitsResponse()))
      .mockResolvedValue(generateCommitsApiResult(generateNotClonedCommitsResponse()));
    const component = await renderTab();
    await expect.element(component.getByText(BEHIND_HEAD)).toBeVisible();

    // WHEN
    useBranch("feature");
    await component.rerender(tab());

    // THEN
    await expect.element(component.getByText("Commit log not available yet")).toBeVisible();
    expect(apiMock).toHaveBeenLastCalledWith(expect.objectContaining({ branchName: "feature" }));
    expect(component.getByTestId("data-table-row").query()).toBeNull();
    expect(component.getByText(BEHIND_HEAD).query()).toBeNull();
  });

  test("loads the next page when the end of the list comes into view", async () => {
    // GIVEN
    apiMock
      .mockResolvedValueOnce(generateCommitsApiResult(generateFirstCommitsPage()))
      .mockResolvedValue(generateCommitsApiResult(generateSecondCommitsPage()));
    const component = await renderTab();
    await expect.element(component.getByText(PAGE_ONE_HEAD)).toBeVisible();
    expect(apiMock).toHaveBeenCalledTimes(1);

    // WHEN
    await component.getByText(PAGE_ONE_LAST).element().scrollIntoView({ block: "end" });

    // THEN
    await expect.element(component.getByText(PAGE_TWO_FIRST)).toBeVisible();
    expect(apiMock).toHaveBeenNthCalledWith(2, expect.objectContaining({ offset: 20, limit: 20 }));
    await expect.element(component.getByText(PAGE_ONE_LAST)).toBeVisible();
    expect(component.getByText(PAGE_ONE_LAST).elements()).toHaveLength(1);
  });

  test("keeps the retry pending while a later page answering unavailable is retried, then offers it", async () => {
    // GIVEN
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"], shouldAdvanceTime: true });
    apiMock
      .mockResolvedValueOnce(generateCommitsApiResult(generateFirstCommitsPage()))
      .mockResolvedValueOnce(generateCommitsApiResult(generateNotClonedCommitsResponse()))
      .mockRejectedValueOnce(new Error("Worker did not answer in time"))
      .mockResolvedValue(generateCommitsApiResult(generateSecondCommitsPage()));
    const component = await renderTab();
    await expect.element(component.getByText(PAGE_ONE_HEAD)).toBeVisible();
    await component.getByText(PAGE_ONE_LAST).element().scrollIntoView({ block: "end" });
    await expect
      .element(component.getByText("Older commits could not be loaded right now."))
      .toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Retry" }))
      .toHaveAttribute("data-pending");
    await expect.element(component.getByText(PAGE_ONE_LAST)).toBeVisible();
    expect(component.getByText(PAGE_TWO_FIRST).query()).toBeNull();
    expect(apiMock).toHaveBeenCalledTimes(2);

    // WHEN
    await vi.advanceTimersByTimeAsync(REPOSITORY_COMMITS_RETRY_DELAY_MS);

    // THEN
    await expect.poll(() => apiMock.mock.calls.length).toBe(3);
    await expect
      .element(component.getByRole("button", { name: "Retry" }))
      .not.toHaveAttribute("data-pending");
    await component.getByRole("button", { name: "Retry" }).click();
    await expect.element(component.getByText(PAGE_TWO_FIRST)).toBeVisible();
    expect(apiMock).toHaveBeenCalledTimes(4);
    expect(apiMock).toHaveBeenNthCalledWith(4, expect.objectContaining({ offset: 20, limit: 20 }));
    expect(component.getByText("Older commits could not be loaded right now.").query()).toBeNull();
  });

  test("offers a retry when loading the next page fails, and loads only that page on retry", async () => {
    // GIVEN
    apiMock
      .mockResolvedValueOnce(generateCommitsApiResult(generateFirstCommitsPage()))
      .mockRejectedValueOnce(new Error("Worker did not answer in time"))
      .mockResolvedValue(generateCommitsApiResult(generateSecondCommitsPage()));
    const component = await renderTab();
    await expect.element(component.getByText(PAGE_ONE_HEAD)).toBeVisible();
    await component.getByText(PAGE_ONE_LAST).element().scrollIntoView({ block: "end" });
    await expect
      .element(component.getByText("Older commits could not be loaded right now."))
      .toBeVisible();
    expect(component.getByText(PAGE_TWO_FIRST).query()).toBeNull();
    expect(apiMock).toHaveBeenCalledTimes(2);

    // WHEN
    await component.getByRole("button", { name: "Retry" }).click();

    // THEN
    await expect.element(component.getByText(PAGE_TWO_FIRST)).toBeVisible();
    expect(apiMock).toHaveBeenCalledTimes(3);
    expect(apiMock).toHaveBeenNthCalledWith(3, expect.objectContaining({ offset: 20, limit: 20 }));
    await expect.element(component.getByText(PAGE_ONE_HEAD)).toBeVisible();
    expect(component.getByText("Older commits could not be loaded right now.").query()).toBeNull();
  });

  test("settles the retry and offers it again when the retry fails too", async () => {
    // GIVEN
    apiMock
      .mockResolvedValueOnce(generateCommitsApiResult(generateFirstCommitsPage()))
      .mockRejectedValue(new Error("Worker did not answer in time"));
    const component = await renderTab();
    await expect.element(component.getByText(PAGE_ONE_HEAD)).toBeVisible();
    await component.getByText(PAGE_ONE_LAST).element().scrollIntoView({ block: "end" });
    await expect.element(component.getByRole("button", { name: "Retry" })).toBeVisible();

    // WHEN
    await component.getByRole("button", { name: "Retry" }).click();

    // THEN
    await expect.poll(() => apiMock.mock.calls.length).toBe(3);
    await expect
      .element(component.getByRole("button", { name: "Retry" }))
      .not.toHaveAttribute("data-pending");
    await expect
      .element(component.getByText("Older commits could not be loaded right now."))
      .toBeVisible();
    await expect.element(component.getByText(PAGE_ONE_HEAD)).toBeVisible();
  });

  test("drops a retry still in flight for the previous branch when the branch changes", async () => {
    // GIVEN
    useBranch("main");
    apiMock
      .mockResolvedValueOnce(generateCommitsApiResult(generateFirstCommitsPage()))
      .mockRejectedValueOnce(new Error("Worker did not answer in time"))
      .mockReturnValueOnce(new Promise<ApiResult>(() => {}))
      .mockResolvedValue(generateCommitsApiResult(generateBehindCommitsResponse()));
    const component = await renderTab();
    await expect.element(component.getByText(PAGE_ONE_HEAD)).toBeVisible();
    await component.getByText(PAGE_ONE_LAST).element().scrollIntoView({ block: "end" });
    await component.getByRole("button", { name: "Retry" }).click();
    await expect.poll(() => apiMock.mock.calls.length).toBe(3);

    // WHEN
    useBranch("feature");
    await component.rerender(tab());

    // THEN
    await expect.element(component.getByText(BEHIND_HEAD)).toBeVisible();
    expect(component.getByRole("button", { name: "Retry" }).query()).toBeNull();
    expect(component.getByText("Older commits could not be loaded right now.").query()).toBeNull();
  });

  test("shows no Retry while a page load after a failed page is in flight", async () => {
    // GIVEN
    let answerNextPage: (result: ApiResult) => void = () => {};
    apiMock
      .mockResolvedValueOnce(generateCommitsApiResult(generateFirstCommitsPage()))
      .mockRejectedValueOnce(new Error("Worker did not answer in time"))
      .mockReturnValueOnce(
        new Promise<ApiResult>((resolve) => {
          answerNextPage = resolve;
        })
      );
    const component = await renderTab();
    await expect.element(component.getByText(PAGE_ONE_HEAD)).toBeVisible();
    await component.getByText(PAGE_ONE_LAST).element().scrollIntoView({ block: "end" });
    await expect.element(component.getByRole("button", { name: "Retry" })).toBeVisible();

    // WHEN
    const nextPage = new InfiniteQueryObserver(
      queryClient,
      getRepositoryCommitsQueryOptions({ repositoryId: "repo-1", branchName: "test-branch" })
    ).fetchNextPage();

    // THEN
    await expect.poll(() => apiMock.mock.calls.length).toBe(3);
    await expect.poll(() => component.getByRole("button", { name: "Retry" }).query()).toBeNull();
    answerNextPage(generateCommitsApiResult(generateSecondCommitsPage()));
    await nextPage;
    await expect.element(component.getByText(PAGE_TWO_FIRST)).toBeVisible();
    expect(component.getByRole("button", { name: "Retry" }).query()).toBeNull();
  });

  test("shows both the check time and the update time when they differ", async () => {
    // GIVEN
    apiMock.mockResolvedValue(generateCommitsApiResult(generateReadOnlyCommitsResponse()));

    // WHEN
    const component = await renderTab();

    // THEN
    await expect
      .element(component.getByText(`Checked ${formatDateTime(READ_ONLY_CHECKED_AT)}`))
      .toBeVisible();
    await expect
      .element(component.getByText(`Updated ${formatDateTime(READ_ONLY_FETCHED_AT)}`))
      .toBeVisible();
    await expect.element(component.getByText("Tracking v1.2.0")).toBeVisible();
  });

  test("shows only the check time when the last check brought the update", async () => {
    // GIVEN
    apiMock.mockResolvedValue(generateCommitsApiResult(generateJustCheckedCommitsResponse()));

    // WHEN
    const component = await renderTab();

    // THEN
    await expect
      .element(component.getByText(`Checked ${formatDateTime(JUST_CHECKED_AT)}`))
      .toBeVisible();
    expect(component.getByText(/Updated/).query()).toBeNull();
  });

  test("shows only the update time when the remote was never checked", async () => {
    // GIVEN
    apiMock.mockResolvedValue(generateCommitsApiResult(generateBehindCommitsResponse()));

    // WHEN
    const component = await renderTab();

    // THEN
    await expect
      .element(component.getByText(`Updated ${formatDateTime("2025-03-10T12:00:00Z")}`))
      .toBeVisible();
    expect(component.getByText(/^Checked /).query()).toBeNull();
  });

  test("renders no total commit count", async () => {
    // GIVEN
    apiMock.mockResolvedValue(generateCommitsApiResult(generateBehindCommitsResponse()));

    // WHEN
    const component = await renderTab();

    // THEN
    await expect.element(component.getByText(BEHIND_HEAD)).toBeVisible();
    expect(component.getByText(/of \d+ results/).query()).toBeNull();
    expect(component.getByText(/\d+ commits$/).query()).toBeNull();
    expect(component.getByText(/^counts?$/).query()).toBeNull();
    const grid = component.getByTestId("data-table-row").first().element().parentElement;
    // Footer cells carry no accessible role; only they carry the sticky-bottom class.
    expect(grid?.querySelectorAll(":scope > .bottom-0")).toHaveLength(0);
    expect(component.getByRole("navigation").query()).toBeNull();
  });
});

type CheckRemoteRefsApiResult = Awaited<ReturnType<typeof checkRemoteRefsFromApi>>;

const checkRemoteRefsApiResult = (taskId: string) =>
  ({
    data: { InfrahubReadOnlyRepositoryCheckRefs: { ok: true, task: { id: taskId } } },
  }) as CheckRemoteRefsApiResult;

type TaskDetailsApiResult = Awaited<ReturnType<typeof checkTaskDetailsFromApi>>;

const ongoingTaskCount = (count: number) =>
  ({ data: { InfrahubTask: { count } } }) as TaskDetailsApiResult;

const CHECK_TASK_ID = "check-task-1";

describe("Check remote now", () => {
  beforeEach(() => {
    useBranch("test-branch");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetAllMocks();
  });

  test("is offered on a read-only repository", async () => {
    // GIVEN
    apiMock.mockResolvedValue(generateCommitsApiResult(generateReadOnlyCommitsResponse()));

    // WHEN
    const component = await renderTab({ isReadOnly: true });

    // THEN
    await expect.element(component.getByRole("button", { name: "Check remote now" })).toBeEnabled();
  });

  test("is not offered on a read-write repository", async () => {
    // GIVEN
    apiMock.mockResolvedValue(generateCommitsApiResult(generateBehindCommitsResponse()));

    // WHEN
    const component = await renderTab();

    // THEN
    await expect.element(component.getByRole("button", { name: "Refresh data" })).toBeVisible();
    expect(component.getByRole("button", { name: "Check remote now" }).query()).toBeNull();
  });

  test("is disabled without permission to update the repository", async () => {
    // GIVEN
    apiMock.mockResolvedValue(generateCommitsApiResult(generateReadOnlyCommitsResponse()));

    // WHEN
    const component = await renderTab({
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
    apiMock.mockResolvedValue(generateCommitsApiResult(generateReadOnlyCommitsResponse()));
    checkRemoteRefsApiMock.mockResolvedValue(checkRemoteRefsApiResult(CHECK_TASK_ID));
    taskDetailsApiMock.mockResolvedValue(ongoingTaskCount(1));
    const component = await renderTab({ isReadOnly: true });
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

  test("shows the new check time beside the older update time once the check ends", async () => {
    // GIVEN
    const checkedBefore = "2025-03-10T18:00:00Z";
    apiMock.mockResolvedValue(
      generateCommitsApiResult({ ...generateReadOnlyCommitsResponse(), checked_at: checkedBefore })
    );
    checkRemoteRefsApiMock.mockResolvedValue(checkRemoteRefsApiResult(CHECK_TASK_ID));
    taskDetailsApiMock.mockResolvedValue(ongoingTaskCount(0));
    const component = await renderTab({ isReadOnly: true });
    await expect
      .element(component.getByText(`Checked ${formatDateTime(checkedBefore)}`))
      .toBeVisible();
    apiMock.mockResolvedValue(generateCommitsApiResult(generateReadOnlyCommitsResponse()));

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
