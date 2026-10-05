import { type QueryClient, useQueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, test, vi } from "vitest";

import { getRepositoryCommitsFromApi } from "@/entities/repository/api/get-repository-commits-from-api";

import { render } from "../../../../tests/components/render";
import {
  generateBehindCommitsResponse,
  generateInSyncCommitsResponse,
  generateNotClonedCommitsResponse,
  type RepositoryCommitsWire,
} from "../../../../tests/fake/repository-commit";
import { RepositoryCommitsManager } from "./repository-commits-manager";
import { RepositoryCommitsTab } from "./repository-commits-tab";

vi.mock("@/entities/repository/api/get-repository-commits-from-api");

const apiMock = vi.mocked(getRepositoryCommitsFromApi);

type ApiResult = Awaited<ReturnType<typeof getRepositoryCommitsFromApi>>;

const apiResult = (response: RepositoryCommitsWire) =>
  ({ data: { InfrahubRepositoryCommits: response } }) as unknown as ApiResult;

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

const expectNoCount = async (component: Awaited<ReturnType<typeof renderTab>>) => {
  await expect.element(component.getByRole("link", { name: "Commits", exact: true })).toBeVisible();
  expect(component.getByText(/pending import/).query()).toBeNull();
  expect(component.getByText(/^\d+$/).query()).toBeNull();
};

describe("RepositoryCommitsTab", () => {
  afterEach(() => {
    vi.resetAllMocks();
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
      .mockResolvedValueOnce(apiResult(generateInSyncCommitsResponse()))
      .mockResolvedValue(apiResult(generateBehindCommitsResponse()));
    const component = await renderTab();
    await expect
      .element(component.getByRole("link", { name: "Commits 0 pending import" }))
      .toBeVisible();

    // WHEN
    await queryClient.refetchQueries();

    // THEN
    await expect
      .element(component.getByRole("link", { name: "Commits 2 pending import" }))
      .toBeVisible();
  });

  test("shares one read with the commit log on screen", async () => {
    // GIVEN
    apiMock.mockResolvedValue(apiResult(generateBehindCommitsResponse()));

    // WHEN
    const component = await render(
      <>
        <RepositoryCommitsTab objectKind="CoreRepository" objectId="repo-1" />
        <RepositoryCommitsManager repositoryId="repo-1" repositoryLocation="/remote/repo" />
      </>
    );

    // THEN
    await expect
      .element(component.getByRole("link", { name: "Commits 2 pending import" }))
      .toBeVisible();
    await expect.element(component.getByText("2 commits pending import")).toBeVisible();
    expect(apiMock).toHaveBeenCalledTimes(1);
  });
});
