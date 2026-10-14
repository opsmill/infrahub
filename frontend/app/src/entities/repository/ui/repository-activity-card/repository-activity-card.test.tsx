import { afterEach, describe, expect, test, vi } from "vitest";

import { RepositoryActivityError } from "@/entities/repository/domain/model/repository-activity";
import { getRepositoryActivity } from "@/entities/repository/domain/use-cases/get-repository-activity";
import {
  ACTIVITY_CHECK_FAILED,
  ACTIVITY_PERMISSION_DENIED,
  RepositoryActivityCard,
} from "@/entities/repository/ui/repository-activity-card/repository-activity-card";

import { render } from "../../../../../tests/components/render";
import {
  generateActiveRun,
  generateActivity,
  generateLastRun,
  generateLock,
  WORKER_ID,
} from "../../../../../tests/fake/repository-activity";

vi.mock("@/entities/repository/domain/use-cases/get-repository-activity");

const textOf = async (component: Awaited<ReturnType<typeof render>>, name: string) =>
  ((await component.getByRole("region", { name }).element()) as HTMLElement).innerText.replace(
    /\s+/g,
    " "
  );

describe("RepositoryActivityCard", () => {
  const getRepositoryActivityMock = vi.mocked(getRepositoryActivity);

  afterEach(() => {
    vi.resetAllMocks();
    vi.useRealTimers();
  });

  test("shows what a run is doing, and the lock in its line and in a sentence below", async () => {
    // GIVEN
    getRepositoryActivityMock.mockResolvedValue(
      generateActivity({
        activeRuns: [
          generateActiveRun({ operation: "SYNC", phase: "APPLYING", branchName: "release-1.12" }),
        ],
        lock: generateLock(),
      })
    );

    // WHEN
    const component = await render(<RepositoryActivityCard repositoryId="repository-1" />);

    // THEN
    await expect.element(component.getByText("Applying release-1.12")).toBeVisible();
    const text = await textOf(component, "Current activity");
    expect(text).toContain(`on worker ${WORKER_ID.slice(0, 8)}`);
    expect(text).toContain("Holds the repository lock (requested");
    expect(text).toContain(
      `Repository lock held by worker ${WORKER_ID.slice(0, 8)} for the sync, requested`
    );
  });

  test("leaves the time out of the lock when the request time cannot be read", async () => {
    // GIVEN
    getRepositoryActivityMock.mockResolvedValue(
      generateActivity({
        activeRuns: [generateActiveRun()],
        lock: generateLock({ requestedAt: null }),
      })
    );

    // WHEN
    const component = await render(<RepositoryActivityCard repositoryId="repository-1" />);

    // THEN
    await expect.element(component.getByText("Applying release-1.12")).toBeVisible();
    const text = await textOf(component, "Current activity");
    expect(text).toContain("Holds the repository lock");
    expect(text).not.toContain("requested");
  });

  test("states a lock held with no active run as a plain fact", async () => {
    // GIVEN
    getRepositoryActivityMock.mockResolvedValue(
      generateActivity({
        lastRuns: [generateLastRun()],
        lock: generateLock({ workerId: "e2a7c9f0-5d13-4b8e-a6f2-91c0d4e8b356" }),
      })
    );

    // WHEN
    const component = await render(<RepositoryActivityCard repositoryId="repository-1" />);

    // THEN
    await expect.element(component.getByText("No activity")).toBeVisible();
    expect(await textOf(component, "Current activity")).toMatch(
      /Repository lock held by worker e2a7c9f0, requested .+, with no active run/
    );
  });

  test("says since when the repository is idle, and nothing about a lock that is not held", async () => {
    // GIVEN
    getRepositoryActivityMock.mockResolvedValue(
      generateActivity({ lastRuns: [generateLastRun({ operation: "MERGE" })] })
    );

    // WHEN
    const component = await render(<RepositoryActivityCard repositoryId="repository-1" />);

    // THEN
    await expect.element(component.getByText("No activity")).toBeVisible();
    const text = await textOf(component, "Current activity");
    expect(text).toContain("Idle since the merge finished");
    expect(text).not.toContain("lock");
  });

  test("says when a repository has not run in the last 30 days", async () => {
    // GIVEN
    getRepositoryActivityMock.mockResolvedValue(generateActivity());

    // WHEN
    const component = await render(<RepositoryActivityCard repositoryId="repository-1" />);

    // THEN
    await expect.element(component.getByText("No run in the last 30 days")).toBeVisible();
    await expect.element(component.getByText("No run finished in the last 30 days")).toBeVisible();
  });

  test("admits a failed check instead of showing the repository as idle", async () => {
    // GIVEN
    getRepositoryActivityMock.mockRejectedValue(new RepositoryActivityError("UNKNOWN", "Offline"));

    // WHEN
    const component = await render(<RepositoryActivityCard repositoryId="repository-1" />);

    // THEN
    await expect.element(component.getByText(ACTIVITY_CHECK_FAILED)).toBeVisible();
    await expect.element(component.getByText("No activity")).not.toBeInTheDocument();
  });

  test("says the viewer has no access when the repository is denied", async () => {
    // GIVEN
    getRepositoryActivityMock.mockRejectedValue(new RepositoryActivityError("NO_ACCESS", "Denied"));

    // WHEN
    const component = await render(<RepositoryActivityCard repositoryId="repository-1" />);

    // THEN
    await expect.element(component.getByText(ACTIVITY_PERMISSION_DENIED)).toBeVisible();
  });

  test("lists the branches a run failed and changed when its line is opened", async () => {
    // GIVEN
    getRepositoryActivityMock.mockResolvedValue(
      generateActivity({
        lastRuns: [
          generateLastRun({
            branches: [
              { branchName: "main", outcome: "IMPORTED" },
              { branchName: "feature-x", outcome: "FAILED" },
            ],
          }),
        ],
      })
    );
    const component = await render(<RepositoryActivityCard repositoryId="repository-1" />);
    await component.getByRole("button", { name: /Last runs/ }).click();

    // WHEN
    await component.getByRole("button", { name: /Sync 1 failed/ }).click();

    // THEN
    await expect.element(component.getByRole("link", { name: "feature-x" })).toBeVisible();
    await expect.element(component.getByRole("link", { name: "main" })).toBeVisible();
  });

  test("counts how long a run has been going, every second", async () => {
    // GIVEN
    vi.useFakeTimers({ now: new Date("2026-10-14T14:01:04Z"), toFake: ["Date", "setInterval"] });
    getRepositoryActivityMock.mockResolvedValue(
      generateActivity({ activeRuns: [generateActiveRun({ startedAt: "2026-10-14T14:00:00Z" })] })
    );
    const component = await render(<RepositoryActivityCard repositoryId="repository-1" />);
    await expect.element(component.getByRole("timer")).toHaveTextContent("1m 04s");

    // WHEN
    vi.advanceTimersByTime(2000);

    // THEN
    await expect.element(component.getByRole("timer")).toHaveTextContent("1m 06s");
  });
});
