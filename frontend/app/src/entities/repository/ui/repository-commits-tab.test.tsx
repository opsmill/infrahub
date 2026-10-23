import { type QueryClient, useQueryClient } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getRepositoryCommitsFromApi } from "@/entities/repository/api/get-repository-commits-from-api";
import {
  READONLY_REPOSITORY_KIND,
  REPOSITORY_INTERNAL_STATUS_STAGING,
  REPOSITORY_KIND,
} from "@/entities/repository/domain/model/repository";
import { REPOSITORY_COMMITS_RETRY_DELAY_MS } from "@/entities/repository/ui/queries/repository-commits.constants";

import { render } from "../../../../tests/components/render";
import { generateBranch } from "../../../../tests/fake/branch";
import {
  generateBehindCommitsResponse,
  generateCommitsApiResult,
  generateInSyncCommitsResponse,
  generateNotClonedCommitsResponse,
  generateRebaseNeededCommitsResponse,
} from "../../../../tests/fake/repository-commit";
import { RepositoryCommitsManager } from "./repository-commits-manager";
import { RepositoryCommitsTab } from "./repository-commits-tab";

vi.mock("@/entities/branches/ui/branches-provider");
vi.mock("@/entities/repository/api/get-repository-commits-from-api");

const apiMock = vi.mocked(getRepositoryCommitsFromApi);

type ApiResult = Awaited<ReturnType<typeof getRepositoryCommitsFromApi>>;

let queryClient: QueryClient;

function CaptureQueryClient() {
  queryClient = useQueryClient();
  return null;
}

const useBranch = ({ syncWithGit }: { syncWithGit: boolean }) =>
  vi.mocked(useCurrentBranch).mockReturnValue({
    currentBranch: generateBranch({ name: "test-branch", sync_with_git: syncWithGit }),
    setCurrentBranch: () => {},
  });

const renderTab = ({
  objectKind = REPOSITORY_KIND,
  internalStatus = "active",
}: {
  objectKind?: string;
  internalStatus?: string;
} = {}) =>
  render(
    <>
      <CaptureQueryClient />
      <RepositoryCommitsTab
        objectKind={objectKind}
        objectId="repo-1"
        internalStatus={internalStatus}
      />
    </>
  );

const expectNoCount = async (component: Awaited<ReturnType<typeof renderTab>>) => {
  await expect.element(component.getByRole("link", { name: "Commits", exact: true })).toBeVisible();
  expect(component.getByText(/pending import/).query()).toBeNull();
  expect(component.getByText(/^\d+$/).query()).toBeNull();
};

describe("RepositoryCommitsTab", () => {
  beforeEach(() => {
    useBranch({ syncWithGit: true });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.resetAllMocks();
  });

  test("shows the pending-import count when the branch is behind", async () => {
    // GIVEN
    apiMock.mockResolvedValue(generateCommitsApiResult(generateBehindCommitsResponse()));

    // WHEN
    const component = await renderTab();

    // THEN
    expect(apiMock).toHaveBeenCalledWith(expect.objectContaining({ repositoryId: "repo-1" }));
    const tab = component.getByRole("link", { name: "Commits 3 pending import" });
    await expect.element(tab).toBeVisible();
    await expect.element(tab.getByText("3")).toBeVisible();
  });

  test("shows 0 when the branch is in sync", async () => {
    // GIVEN
    apiMock.mockResolvedValue(generateCommitsApiResult(generateInSyncCommitsResponse()));

    // WHEN
    const component = await renderTab();

    // THEN
    await expect
      .element(component.getByRole("link", { name: "Commits 0 pending import" }))
      .toBeVisible();
  });

  describe("on a branch that does not sync with Git", () => {
    beforeEach(() => {
      useBranch({ syncWithGit: false });
    });

    test.each([
      { condition: "behind", response: generateRebaseNeededCommitsResponse, count: 2 },
      { condition: "in sync", response: generateInSyncCommitsResponse, count: 0 },
    ])(
      "counts the commits behind main when the branch is $condition",
      async ({ response, count }) => {
        // GIVEN
        apiMock.mockResolvedValue(generateCommitsApiResult(response()));

        // WHEN
        const component = await renderTab();

        // THEN
        await expect
          .element(component.getByRole("link", { name: `Commits ${count} behind` }))
          .toBeVisible();
      }
    );

    test.each([
      { case: "a read-only repository", objectKind: READONLY_REPOSITORY_KIND },
      {
        case: "a repository added on the branch",
        internalStatus: REPOSITORY_INTERNAL_STATUS_STAGING,
      },
    ])("counts the commits pending import for $case", async ({ objectKind, internalStatus }) => {
      // GIVEN
      apiMock.mockResolvedValue(generateCommitsApiResult(generateBehindCommitsResponse()));

      // WHEN
      const component = await renderTab({ objectKind, internalStatus });

      // THEN
      await expect
        .element(component.getByRole("link", { name: "Commits 3 pending import" }))
        .toBeVisible();
    });
  });

  test("shows no count when no worker holds a copy", async () => {
    // GIVEN
    apiMock.mockResolvedValue(generateCommitsApiResult(generateNotClonedCommitsResponse()));

    // WHEN
    const component = await renderTab();

    // THEN
    await expectNoCount(component);
  });

  test("shows no spinner while it retries an unavailable answer", async () => {
    // GIVEN
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"], shouldAdvanceTime: true });
    apiMock
      .mockResolvedValueOnce(generateCommitsApiResult(generateNotClonedCommitsResponse()))
      .mockReturnValueOnce(new Promise<ApiResult>(() => {}));
    const component = await renderTab();
    await expect.poll(() => apiMock.mock.calls.length).toBe(1);
    await expect.poll(() => component.getByRole("status").query()).toBeNull();

    // WHEN
    await vi.advanceTimersByTimeAsync(REPOSITORY_COMMITS_RETRY_DELAY_MS);

    // THEN
    expect(apiMock).toHaveBeenCalledTimes(2);
    expect(component.getByRole("status").query()).toBeNull();
    await expectNoCount(component);
  });

  test("shows no count when the repository cannot be read", async () => {
    // GIVEN
    apiMock.mockRejectedValue(
      new Error("Unable to find the node repo-1 / CoreRepository in the database.")
    );

    // WHEN
    const component = await renderTab();

    // THEN
    await expect.poll(() => apiMock.mock.calls.length).toBe(1);
    await expectNoCount(component);
  });

  test("follows the count of the latest commit log", async () => {
    // GIVEN
    apiMock
      .mockResolvedValueOnce(generateCommitsApiResult(generateInSyncCommitsResponse()))
      .mockResolvedValue(generateCommitsApiResult(generateBehindCommitsResponse()));
    const component = await renderTab();
    await expect
      .element(component.getByRole("link", { name: "Commits 0 pending import" }))
      .toBeVisible();

    // WHEN
    await queryClient.refetchQueries();

    // THEN
    await expect
      .element(component.getByRole("link", { name: "Commits 3 pending import" }))
      .toBeVisible();
  });

  test("shares one read with the commit log on screen", async () => {
    // GIVEN
    apiMock.mockResolvedValue(generateCommitsApiResult(generateBehindCommitsResponse()));

    // WHEN
    const component = await render(
      <>
        <RepositoryCommitsTab
          objectKind={REPOSITORY_KIND}
          objectId="repo-1"
          internalStatus="active"
        />
        <RepositoryCommitsManager
          repositoryId="repo-1"
          repositoryKind={REPOSITORY_KIND}
          repositoryInternalStatus="active"
          repositoryLocation="/remote/repo"
          remoteCheck={null}
        />
      </>
    );

    // THEN
    await expect
      .element(component.getByRole("link", { name: "Commits 3 pending import" }))
      .toBeVisible();
    await expect.element(component.getByText("3 commits pending import")).toBeVisible();
    expect(apiMock).toHaveBeenCalledTimes(1);
  });
});
