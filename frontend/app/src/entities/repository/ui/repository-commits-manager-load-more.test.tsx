import { type QueryClient, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getRepositoryCommitsFromApi } from "@/entities/repository/api/get-repository-commits-from-api";

import { render } from "../../../../tests/components/render";
import { generateBranch } from "../../../../tests/fake/branch";
import {
  BEHIND_HEAD,
  generateBehindCommitsResponse,
  generateFirstCommitsPage,
  generateSecondCommitsPage,
  PAGE_ONE_HEAD,
  type RepositoryCommitsWire,
} from "../../../../tests/fake/repository-commit";
import { RepositoryCommitsManager } from "./repository-commits-manager";

vi.mock("@/entities/branches/ui/branches-provider");
vi.mock("@/entities/repository/api/get-repository-commits-from-api");
// Exposes onLoadMore as a button: the scroll sentinel cannot be made to fire while a refresh is pending.
vi.mock("@/shared/components/utils/infinite-scroll", () => ({
  InfiniteScroll: ({ children, onLoadMore }: { children: ReactNode; onLoadMore: () => void }) => (
    <div>
      {children}
      <button type="button" onClick={onLoadMore}>
        Load more
      </button>
    </div>
  ),
}));

const apiMock = vi.mocked(getRepositoryCommitsFromApi);

type ApiResult = Awaited<ReturnType<typeof getRepositoryCommitsFromApi>>;

const apiResult = (response: RepositoryCommitsWire) =>
  ({ data: { InfrahubRepositoryCommits: response } }) as unknown as ApiResult;

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

  test("does not cancel a refresh still in progress when more commits are requested", async () => {
    // GIVEN
    let answerRefresh: (value: ApiResult) => void = () => {};
    apiMock
      .mockResolvedValueOnce(apiResult(generateFirstCommitsPage()))
      .mockImplementationOnce(
        () =>
          new Promise<ApiResult>((resolve) => {
            answerRefresh = resolve;
          })
      )
      .mockResolvedValue(apiResult(generateSecondCommitsPage()));
    const component = await render(
      <>
        <CaptureQueryClient />
        <RepositoryCommitsManager repositoryId="repo-1" repositoryLocation={null} />
      </>
    );
    await expect.element(component.getByText(PAGE_ONE_HEAD)).toBeVisible();
    const refresh = queryClient.refetchQueries();
    await expect.poll(() => apiMock.mock.calls.length).toBe(2);

    // WHEN
    await component.getByRole("button", { name: "Load more" }).click();
    answerRefresh(apiResult(generateBehindCommitsResponse()));

    // THEN
    await refresh;
    await expect.element(component.getByText(BEHIND_HEAD)).toBeVisible();
  });
});
