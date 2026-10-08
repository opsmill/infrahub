import { type QueryClient, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getRepositoryCommitsFromApi } from "@/entities/repository/api/get-repository-commits-from-api";

import { render } from "../../../../tests/components/render";
import { generateBranch } from "../../../../tests/fake/branch";
import {
  generateCommitsApiResult,
  generateFirstCommitsPage,
  PAGE_ONE_HEAD,
} from "../../../../tests/fake/repository-commit";
import { RepositoryCommitsManager } from "./repository-commits-manager";

vi.mock("@/entities/branches/ui/branches-provider");
vi.mock("@/entities/repository/api/get-repository-commits-from-api");
// Renders the load trigger as a button so the test can read whether older commits may load.
vi.mock("@/shared/components/utils/infinite-scroll", () => ({
  InfiniteScroll: ({
    children,
    hasNextPage,
    onLoadMore,
  }: {
    children: ReactNode;
    hasNextPage: boolean;
    onLoadMore: () => void;
  }) => (
    <div>
      {children}
      {hasNextPage && (
        <button type="button" onClick={onLoadMore}>
          Load more
        </button>
      )}
    </div>
  ),
}));

const apiMock = vi.mocked(getRepositoryCommitsFromApi);

type ApiResult = Awaited<ReturnType<typeof getRepositoryCommitsFromApi>>;

const STALE_NOTICE =
  "Couldn't refresh the commit log right now. Showing the last loaded commits; older commits load after a successful refresh.";

let queryClient: QueryClient;

function CaptureQueryClient() {
  queryClient = useQueryClient();
  return null;
}

describe("RepositoryCommitsManager loading more", () => {
  beforeEach(() => {
    vi.mocked(useCurrentBranch).mockReturnValue({
      currentBranch: generateBranch({ name: "main" }),
      setCurrentBranch: () => {},
    });
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  test("offers older commits again only once a running refresh has answered", async () => {
    // GIVEN
    let answerRefresh: (value: ApiResult) => void = () => {};
    apiMock
      .mockResolvedValueOnce(generateCommitsApiResult(generateFirstCommitsPage()))
      .mockImplementationOnce(
        () =>
          new Promise<ApiResult>((resolve) => {
            answerRefresh = resolve;
          })
      );
    const component = await render(
      <>
        <CaptureQueryClient />
        <RepositoryCommitsManager repositoryId="repo-1" repositoryLocation={null} />
      </>
    );
    await expect.element(component.getByRole("button", { name: "Load more" })).toBeVisible();

    // WHEN
    const refresh = queryClient.refetchQueries();
    await expect.poll(() => apiMock.mock.calls.length).toBe(2);

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Load more" }))
      .not.toBeInTheDocument();
    answerRefresh(generateCommitsApiResult(generateFirstCommitsPage()));
    await refresh;
    await expect.element(component.getByRole("button", { name: "Load more" })).toBeVisible();
  });

  test("offers no older commits after a refresh that failed", async () => {
    // GIVEN
    apiMock
      .mockResolvedValueOnce(generateCommitsApiResult(generateFirstCommitsPage()))
      .mockRejectedValueOnce(new Error("Network down"));
    const component = await render(
      <>
        <CaptureQueryClient />
        <RepositoryCommitsManager repositoryId="repo-1" repositoryLocation={null} />
      </>
    );
    await expect.element(component.getByText(PAGE_ONE_HEAD)).toBeVisible();

    // WHEN
    await queryClient.refetchQueries();

    // THEN
    await expect.element(component.getByText(STALE_NOTICE)).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Load more" }))
      .not.toBeInTheDocument();
  });
});
