import { type QueryClient, useQueryClient } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { userEvent } from "vitest/browser";

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
  generateOrphanedCommitsResponse,
  generateReadOnlyCommitsResponse,
  generateRebaseNeededCommitsResponse,
  generateRewrittenCommitsResponse,
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
  expect(component.getByText(/^\d+$/).query()).toBeNull();
};

// Parks the pointer beside the tab, since the shared helper clicks the top-left corner, which is on the tab.
const parkPointer = (component: Awaited<ReturnType<typeof renderTab>>) =>
  component.locator.click({ position: { x: 600, y: 1 } });

const hoverTab = async (component: Awaited<ReturnType<typeof renderTab>>, name: string) => {
  await parkPointer(component);
  await component.getByRole("link", { name }).hover();
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
    const tab = component.getByRole("link", { name: "Commits, 3 commits pending import" });
    await expect.element(tab).toBeVisible();
    await expect.element(tab.getByText("3", { exact: true })).toBeVisible();
  });

  test("says the next sync imports the pending commits", async () => {
    // GIVEN
    apiMock.mockResolvedValue(generateCommitsApiResult(generateBehindCommitsResponse()));
    const component = await renderTab();

    // WHEN
    await hoverTab(component, "Commits, 3 commits pending import");

    // THEN
    await expect
      .element(
        component.getByRole("tooltip", {
          name: "3 commits pending import — the next sync imports them",
        })
      )
      .toBeVisible();
    await parkPointer(component);
  });

  test("opens the tooltip when the tab receives keyboard focus", async () => {
    // GIVEN
    apiMock.mockResolvedValue(generateCommitsApiResult(generateBehindCommitsResponse()));
    const component = await renderTab();
    await expect
      .element(component.getByRole("link", { name: "Commits, 3 commits pending import" }))
      .toBeVisible();

    // WHEN
    await userEvent.tab();

    // THEN
    await expect
      .element(
        component.getByRole("tooltip", {
          name: "3 commits pending import — the next sync imports them",
        })
      )
      .toBeVisible();
  });

  test("closes the open tooltip on Escape", async () => {
    // GIVEN
    apiMock.mockResolvedValue(generateCommitsApiResult(generateBehindCommitsResponse()));
    const component = await renderTab();
    await expect
      .element(component.getByRole("link", { name: "Commits, 3 commits pending import" }))
      .toBeVisible();
    await userEvent.tab();
    const tooltip = component.getByRole("tooltip", {
      name: "3 commits pending import — the next sync imports them",
    });
    await expect.element(tooltip).toBeVisible();

    // WHEN
    await userEvent.keyboard("{Escape}");

    // THEN
    await expect.element(tooltip).not.toBeInTheDocument();
  });

  test("caps a large count and keeps the exact number in the accessible name", async () => {
    // GIVEN
    apiMock.mockResolvedValue(
      generateCommitsApiResult({ ...generateBehindCommitsResponse(), pending_count: 1284 })
    );

    // WHEN
    const component = await renderTab();

    // THEN
    const tab = component.getByRole("link", { name: "Commits, 1,284 commits pending import" });
    await expect.element(tab).toBeVisible();
    await expect.element(tab.getByText("999+")).toBeVisible();
  });

  test("shows no count when the branch is in sync", async () => {
    // GIVEN
    apiMock.mockResolvedValue(generateCommitsApiResult(generateInSyncCommitsResponse()));

    // WHEN
    const component = await renderTab();

    // THEN
    await expect.poll(() => apiMock.mock.calls.length).toBe(1);
    await expectNoCount(component);
  });

  test.each([
    {
      condition: "the tracked ref was rewritten",
      response: generateRewrittenCommitsResponse,
      name: "Commits, history rewritten",
    },
    {
      condition: "the imported commit is missing from the remote",
      response: generateOrphanedCommitsResponse,
      name: "Commits, imported commit missing",
    },
  ])("warns without a count when $condition", async ({ response, name }) => {
    // GIVEN
    apiMock.mockResolvedValue(generateCommitsApiResult(response()));

    // WHEN
    const component = await renderTab();

    // THEN
    await expect.element(component.getByRole("link", { name })).toBeVisible();
    expect(component.getByText(/^\d+$/).query()).toBeNull();
  });

  describe("on a rebase-only branch", () => {
    beforeEach(() => {
      useBranch({ syncWithGit: false });
    });

    test("counts the commits behind main and asks for a rebase", async () => {
      // GIVEN
      apiMock.mockResolvedValue(generateCommitsApiResult(generateRebaseNeededCommitsResponse()));
      const component = await renderTab();

      // WHEN
      await hoverTab(component, "Commits, 2 commits behind main");

      // THEN
      await expect
        .element(
          component.getByRole("tooltip", {
            name: "2 commits behind main — rebase the branch to use them",
          })
        )
        .toBeVisible();
      await parkPointer(component);
    });

    test("says the branch has diverged when the tracked ref was rewritten", async () => {
      // GIVEN
      apiMock.mockResolvedValue(generateCommitsApiResult(generateRewrittenCommitsResponse()));

      // WHEN
      const component = await renderTab();

      // THEN
      await expect
        .element(component.getByRole("link", { name: "Commits, diverged from main" }))
        .toBeVisible();
    });

    test("asks for Import latest commit on a read-only repository", async () => {
      // GIVEN
      apiMock.mockResolvedValue(generateCommitsApiResult(generateReadOnlyCommitsResponse()));
      const component = await renderTab({ objectKind: READONLY_REPOSITORY_KIND });

      // WHEN
      await hoverTab(component, "Commits, 1 commit pending import");

      // THEN
      await expect
        .element(
          component.getByRole("tooltip", {
            name: "1 commit pending import — run Import latest commit to use it",
          })
        )
        .toBeVisible();
      await parkPointer(component);
    });

    test("says the next sync imports the commits of a repository added on the branch", async () => {
      // GIVEN
      apiMock.mockResolvedValue(generateCommitsApiResult(generateBehindCommitsResponse()));
      const component = await renderTab({ internalStatus: REPOSITORY_INTERNAL_STATUS_STAGING });

      // WHEN
      await hoverTab(component, "Commits, 3 commits pending import");

      // THEN
      await expect
        .element(
          component.getByRole("tooltip", {
            name: "3 commits pending import — the next sync imports them",
          })
        )
        .toBeVisible();
      await parkPointer(component);
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
    await expectNoCount(component);

    // WHEN
    await queryClient.refetchQueries();

    // THEN
    await expect
      .element(component.getByRole("link", { name: "Commits, 3 commits pending import" }))
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
      .element(component.getByRole("link", { name: "Commits, 3 commits pending import" }))
      .toBeVisible();
    await expect.element(component.getByText("3 commits pending import")).toBeVisible();
    expect(apiMock).toHaveBeenCalledTimes(1);
  });
});
