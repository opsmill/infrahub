import { type QueryClient, useQueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, test, vi } from "vitest";

import { queryClient as appQueryClient } from "@/shared/api/rest/client";

import { getRepositoryCommitStatusFromApi } from "@/entities/repository/api/get-repository-commit-status-from-api";
import { getRepositoryCommitsFromApi } from "@/entities/repository/api/get-repository-commits-from-api";
import { getRepositoryCommitsQueryOptions } from "@/entities/repository/ui/queries/get-repository-commits.query";

import { render } from "../../../../tests/components/render";
import { generateBranch } from "../../../../tests/fake/branch";
import {
  generateBehindCommitsResponse,
  generateInSyncCommitsResponse,
  generateNotClonedCommitsResponse,
  type RepositoryCommitsWire,
} from "../../../../tests/fake/repository-commit";
import { RepositoryCommitsManager } from "./repository-commits-manager";
import { RepositoryCommitsTab } from "./repository-commits-tab";

vi.mock("@/entities/repository/api/get-repository-commit-status-from-api");
vi.mock("@/entities/repository/api/get-repository-commits-from-api");

const apiMock = vi.mocked(getRepositoryCommitStatusFromApi);
const commitsApiMock = vi.mocked(getRepositoryCommitsFromApi);

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

const renderTabWithCommitLog = () => {
  window.history.pushState({}, "", COMMITS_TAB_PATH);
  return render(
    <>
      <CaptureQueryClient />
      <RepositoryCommitsTab objectKind="CoreRepository" objectId="repo-1" />
      <RepositoryCommitsManager repositoryId="repo-1" repositoryLocation="/remote/repo" />
    </>
  );
};

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

  test("refreshes the commit log without a separate status read", async () => {
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
