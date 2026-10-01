import { type QueryClient, useQueryClient } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { queryClient as appQueryClient } from "@/shared/api/rest/client";
import { formatWithPreferences } from "@/shared/context/date-preferences-context";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getRepositoryCommitsFromApi } from "@/entities/repository/api/get-repository-commits-from-api";
import type { RepositoryGitCondition } from "@/entities/repository/domain/model/repository";

import { render } from "../../../../tests/components/render";
import { generateBranch } from "../../../../tests/fake/branch";
import {
  BEHIND_HEAD,
  BEHIND_IMPORTED,
  fullHash,
  generateBehindCommitsResponse,
  generateFirstCommitsPage,
  generateInSyncCommitsResponse,
  generateJustCheckedCommitsResponse,
  generateNotClonedCommitsResponse,
  generateOrphanedCommitsResponse,
  generateReadOnlyCommitsResponse,
  generateRepositoryCommitsResponse,
  generateRewrittenCommitsResponse,
  generateSecondCommitsPage,
  IN_SYNC_HEAD,
  JUST_CHECKED_AT,
  NOT_CLONED_MESSAGE,
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

const apiMock = vi.mocked(getRepositoryCommitsFromApi);
const useCurrentBranchMock = vi.mocked(useCurrentBranch);

type ApiResult = Awaited<ReturnType<typeof getRepositoryCommitsFromApi>>;

const apiResult = (response: RepositoryCommitsWire) =>
  ({ data: { InfrahubRepositoryCommits: response } }) as unknown as ApiResult;

const formatDate = (date: string) =>
  formatWithPreferences(date, { pattern: null, timezone: null }, "date");
const formatDateTime = (date: string) =>
  formatWithPreferences(date, { pattern: null, timezone: null }, "datetime");

let queryClient: QueryClient;

function CaptureQueryClient() {
  queryClient = useQueryClient();
  return null;
}

const tab = () => (
  <>
    <CaptureQueryClient />
    {/* Bounded like the tab panel, or the scroll sentinel can start in view and load page two on its own. */}
    <div className="h-96">
      <RepositoryCommitsManager
        repositoryId="repo-1"
        repositoryLocation="https://github.com/opsmill/infrahub-demo.git"
      />
    </div>
  </>
);

const renderTab = () => render(tab());

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
    vi.restoreAllMocks();
    vi.resetAllMocks();
    vi.unstubAllGlobals();
    Object.defineProperty(navigator, "clipboard", { value: undefined, configurable: true });
  });

  test("renders every commit field newest-first as returned", async () => {
    // GIVEN
    apiMock.mockResolvedValue(apiResult(generateBehindCommitsResponse()));

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
    apiMock.mockResolvedValue(apiResult(generateBehindCommitsResponse()));

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
    apiMock.mockResolvedValue(apiResult(generateInSyncCommitsResponse()));

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
    apiMock.mockResolvedValue(apiResult(generateRewrittenCommitsResponse()));

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
    apiMock.mockResolvedValue(apiResult(response));

    // WHEN
    const component = await renderTab();

    // THEN
    for (const text of texts) {
      await expect.element(component.getByText(text)).toBeVisible();
    }
  });

  test("renders the not-yet-available message when no worker holds a copy", async () => {
    // GIVEN
    apiMock.mockResolvedValue(apiResult(generateNotClonedCommitsResponse()));

    // WHEN
    const component = await renderTab();

    // THEN
    await expect.element(component.getByText("Commit log not available yet")).toBeVisible();
    await expect.element(component.getByText(NOT_CLONED_MESSAGE)).toBeVisible();
    expect(component.getByText("Sorry, something went wrong.").query()).toBeNull();
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

  test("offers a refresh on the error screen when the first load fails", async () => {
    // GIVEN
    apiMock.mockRejectedValue(new Error("Worker did not answer in time"));

    // WHEN
    const component = await renderTab();

    // THEN
    await expect.element(component.getByText("Worker did not answer in time")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Refresh data" })).toBeVisible();
  });

  test("renders the error screen when a poll fails after an unavailable answer", async () => {
    // GIVEN
    apiMock
      .mockResolvedValueOnce(apiResult(generateNotClonedCommitsResponse()))
      .mockRejectedValue(new Error("Worker did not answer in time"));
    const component = await renderTab();
    await expect.element(component.getByText("Commit log not available yet")).toBeVisible();

    // WHEN
    await queryClient.refetchQueries();

    // THEN
    await expect.element(component.getByText("Worker did not answer in time")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Refresh data" })).toBeVisible();
    expect(component.getByText("Commit log not available yet").query()).toBeNull();
  });

  test("refetches the log when refresh is pressed on the error screen", async () => {
    // GIVEN
    apiMock
      .mockRejectedValueOnce(new Error("Worker did not answer in time"))
      .mockResolvedValue(apiResult(generateBehindCommitsResponse()));
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

  test("keeps the loaded rows when a later poll answers unavailable", async () => {
    // GIVEN
    apiMock
      .mockResolvedValueOnce(apiResult(generateBehindCommitsResponse()))
      .mockResolvedValue(apiResult(generateNotClonedCommitsResponse()));
    const component = await renderTab();
    await expect.element(component.getByText(BEHIND_HEAD)).toBeVisible();

    // WHEN
    await queryClient.refetchQueries();

    // THEN
    expect(apiMock).toHaveBeenCalledTimes(2);
    await expect.element(component.getByText(BEHIND_HEAD)).toBeVisible();
    await expect.element(component.getByText(BEHIND_IMPORTED)).toBeVisible();
    expect(component.getByText("Commit log not available yet").query()).toBeNull();
  });

  test("keeps the loaded rows when a later poll fails", async () => {
    // GIVEN
    apiMock
      .mockResolvedValueOnce(apiResult(generateBehindCommitsResponse()))
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

  test("replaces the not-yet-available state with the rows once a worker answers", async () => {
    // GIVEN
    apiMock
      .mockResolvedValueOnce(apiResult(generateNotClonedCommitsResponse()))
      .mockResolvedValue(apiResult(generateBehindCommitsResponse()));
    const component = await renderTab();
    await expect.element(component.getByText("Commit log not available yet")).toBeVisible();

    // WHEN
    await queryClient.refetchQueries();

    // THEN
    await expect.element(component.getByText(BEHIND_HEAD)).toBeVisible();
    await expect.element(component.getByText(BEHIND_IMPORTED)).toBeVisible();
    expect(component.getByText("Commit log not available yet").query()).toBeNull();
  });

  test("drops the previous branch's rows when the branch changes", async () => {
    // GIVEN
    useBranch("main");
    apiMock
      .mockResolvedValueOnce(apiResult(generateBehindCommitsResponse()))
      .mockResolvedValue(apiResult(generateNotClonedCommitsResponse()));
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
      .mockResolvedValueOnce(apiResult(generateFirstCommitsPage()))
      .mockResolvedValue(apiResult(generateSecondCommitsPage()));
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

  test("still loads the next page after a poll answered unavailable", async () => {
    // GIVEN
    apiMock
      .mockResolvedValueOnce(apiResult(generateFirstCommitsPage()))
      .mockResolvedValueOnce(apiResult(generateNotClonedCommitsResponse()))
      .mockResolvedValue(apiResult(generateSecondCommitsPage()));
    const component = await renderTab();
    await expect.element(component.getByText(PAGE_ONE_HEAD)).toBeVisible();
    await queryClient.refetchQueries();
    await expect.element(component.getByText(PAGE_ONE_HEAD)).toBeVisible();

    // WHEN
    await component.getByText(PAGE_ONE_LAST).element().scrollIntoView({ block: "end" });

    // THEN
    await expect.element(component.getByText(PAGE_TWO_FIRST)).toBeVisible();
    expect(apiMock).toHaveBeenNthCalledWith(3, expect.objectContaining({ offset: 20, limit: 20 }));
  });

  test("offers a retry when a later page answers unavailable, and loads it on retry", async () => {
    // GIVEN
    apiMock
      .mockResolvedValueOnce(apiResult(generateFirstCommitsPage()))
      .mockResolvedValueOnce(apiResult(generateNotClonedCommitsResponse()))
      .mockResolvedValueOnce(apiResult(generateFirstCommitsPage()))
      .mockResolvedValue(apiResult(generateSecondCommitsPage()));
    const component = await renderTab();
    await expect.element(component.getByText(PAGE_ONE_HEAD)).toBeVisible();
    await component.getByText(PAGE_ONE_LAST).element().scrollIntoView({ block: "end" });
    await expect
      .element(component.getByText("Older commits could not be loaded right now."))
      .toBeVisible();
    await expect.element(component.getByText(PAGE_ONE_LAST)).toBeVisible();
    expect(component.getByText(PAGE_TWO_FIRST).query()).toBeNull();
    expect(apiMock).toHaveBeenCalledTimes(2);

    // WHEN
    await component.getByRole("button", { name: "Retry" }).click();

    // THEN
    await expect.element(component.getByText(PAGE_TWO_FIRST)).toBeVisible();
    expect(apiMock).toHaveBeenCalledTimes(4);
    expect(apiMock).toHaveBeenNthCalledWith(4, expect.objectContaining({ offset: 20, limit: 20 }));
    expect(component.getByText("Older commits could not be loaded right now.").query()).toBeNull();
  });

  test("offers a retry when loading the next page fails, and loads only that page on retry", async () => {
    // GIVEN
    apiMock
      .mockResolvedValueOnce(apiResult(generateFirstCommitsPage()))
      .mockRejectedValueOnce(new Error("Worker did not answer in time"))
      .mockResolvedValue(apiResult(generateSecondCommitsPage()));
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

  test("shows both the check time and the update time when they differ", async () => {
    // GIVEN
    apiMock.mockResolvedValue(apiResult(generateReadOnlyCommitsResponse()));

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
    apiMock.mockResolvedValue(apiResult(generateJustCheckedCommitsResponse()));

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
    apiMock.mockResolvedValue(apiResult(generateBehindCommitsResponse()));

    // WHEN
    const component = await renderTab();

    // THEN
    await expect
      .element(component.getByText(`Updated ${formatDateTime("2025-03-10T12:00:00Z")}`))
      .toBeVisible();
    expect(component.getByText(/^Checked /).query()).toBeNull();
  });

  test("copies the full hash and announces it", async () => {
    // GIVEN
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("isSecureContext", true);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    apiMock.mockResolvedValue(apiResult(generateBehindCommitsResponse()));
    const component = await renderTab();

    // WHEN
    await component.getByRole("button", { name: `Actions for commit ${BEHIND_HEAD}` }).click();
    await component.getByRole("menuitem", { name: "Copy commit hash" }).click();

    // THEN
    expect(writeText).toHaveBeenCalledWith(fullHash(BEHIND_HEAD));
    await expect
      .element(component.getByRole("status").filter({ hasText: "Copied to clipboard" }))
      .toHaveTextContent("Copied to clipboard");
  });

  test("renders no total commit count", async () => {
    // GIVEN
    apiMock.mockResolvedValue(apiResult(generateBehindCommitsResponse()));

    // WHEN
    const component = await renderTab();

    // THEN
    await expect.element(component.getByText(BEHIND_HEAD)).toBeVisible();
    expect(component.getByText(/of \d+ results/).query()).toBeNull();
    expect(component.getByText(/\d+ commits$/).query()).toBeNull();
    expect(component.getByText(/\d+ counts?$/).query()).toBeNull();
  });
});
