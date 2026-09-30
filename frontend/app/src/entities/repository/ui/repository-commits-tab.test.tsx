import { type QueryClient, useQueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, test, vi } from "vitest";

import { formatWithPreferences } from "@/shared/context/date-preferences-context";

import { getRepositoryCommitsFromApi } from "@/entities/repository/api/get-repository-commits-from-api";

import { render } from "../../../../tests/components/render";
import {
  BEHIND_HEAD,
  BEHIND_IMPORTED,
  fullHash,
  generateBehindCommitsResponse,
  generateInSyncCommitsResponse,
  generateNotClonedCommitsResponse,
  generateReadOnlyCommitsResponse,
  generateRewrittenCommitsResponse,
  IN_SYNC_HEAD,
  NOT_CLONED_MESSAGE,
  READ_ONLY_CHECKED_AT,
  READ_ONLY_FETCHED_AT,
  type RepositoryCommitsWire,
} from "../../../../tests/fake/repository-commit";
import { RepositoryCommitsTab } from "./repository-commits-tab";

vi.mock("@/entities/repository/api/get-repository-commits-from-api");

const apiMock = vi.mocked(getRepositoryCommitsFromApi);

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

const renderTab = () =>
  render(
    <>
      <CaptureQueryClient />
      <RepositoryCommitsTab objectId="repo-1" />
    </>
  );

describe("RepositoryCommitsTab", () => {
  afterEach(() => {
    vi.resetAllMocks();
    vi.restoreAllMocks();
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
      .element(component.getByRole("status").filter({ hasText: "The tracked ref was rewritten" }))
      .toBeVisible();
    expect(component.getByText(/pending import/i).query()).toBeNull();
    const rows = component.getByTestId("data-table-row");
    await expect.element(rows.nth(1).getByText("Not on current history")).toBeVisible();
    await expect.element(rows.nth(2).getByText("Not on current history")).toBeVisible();
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
    await component.getByRole("button", { name: `Copy full hash ${BEHIND_HEAD}` }).click();

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
