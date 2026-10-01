import { afterEach, describe, expect, test, vi } from "vitest";

import { getRepositoryCommitsFromApi } from "@/entities/repository/api/get-repository-commits-from-api";

import { render } from "../../../../tests/components/render";
import {
  generateBehindCommitsResponse,
  generateInSyncCommitsResponse,
  generateNotClonedCommitsResponse,
  type RepositoryCommitsWire,
} from "../../../../tests/fake/repository-commit";
import { RepositoryCommitsTab } from "./repository-commits-tab";

vi.mock("@/entities/repository/api/get-repository-commits-from-api");

const apiMock = vi.mocked(getRepositoryCommitsFromApi);

type ApiResult = Awaited<ReturnType<typeof getRepositoryCommitsFromApi>>;

const apiResult = (response: RepositoryCommitsWire) =>
  ({ data: { InfrahubRepositoryCommits: response } }) as unknown as ApiResult;

const renderTab = () =>
  render(<RepositoryCommitsTab objectKind="CoreRepository" objectId="repo-1" />);

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
});
