import { afterEach, describe, expect, test, vi } from "vitest";

import { getRepositoryActivity } from "@/entities/repository/domain/use-cases/get-repository-activity";
import {
  ACTIVITY_LOAD_FAILED,
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

const textOf = (component: Awaited<ReturnType<typeof render>>) =>
  component.container.innerText.replace(/\s+/g, " ");

describe("RepositoryActivityCard", () => {
  const getRepositoryActivityMock = vi.mocked(getRepositoryActivity);

  afterEach(() => {
    vi.resetAllMocks();
    vi.useRealTimers();
  });

  test("shows what a run is doing, and names only the worker that holds the lock", async () => {
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
    const text = textOf(component);
    expect(text).toContain(`on worker ${WORKER_ID}`);
    expect(text).toContain(`Repository lock held by worker ${WORKER_ID}, requested`);
    expect(text).not.toContain("with no active run");
    expect(text).not.toContain("Holds the repository lock");
    expect(text).not.toContain("for the sync");
  });

  test("names no run as the lock holder when several runs share the lock's worker", async () => {
    // GIVEN
    getRepositoryActivityMock.mockResolvedValue(
      generateActivity({
        activeRuns: [
          generateActiveRun({
            runId: "run-1",
            operation: "SYNC",
            phase: "BUILDING",
            branchName: "main",
          }),
          generateActiveRun({
            runId: "run-2",
            operation: "REIMPORT",
            phase: "APPLYING",
            branchName: "feature-x",
          }),
        ],
        lock: generateLock(),
      })
    );

    // WHEN
    const component = await render(<RepositoryActivityCard repositoryId="repository-1" />);

    // THEN
    await expect.element(component.getByText("Applying feature-x")).toBeVisible();
    const text = textOf(component);
    expect(text).toContain(`Repository lock held by worker ${WORKER_ID}, requested`);
    expect(text).not.toMatch(/for the (sync|reimport)/);
    expect(text).not.toContain("with no active run");
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
    const text = textOf(component);
    expect(text).toContain(`Repository lock held by worker ${WORKER_ID}`);
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
    expect(textOf(component)).toMatch(
      /Repository lock held by worker e2a7c9f0-5d13-4b8e-a6f2-91c0d4e8b356, requested .+, with no active run/
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
    const text = textOf(component);
    expect(text).toContain("Idle since the merge finished");
    expect(text).not.toContain("lock");
  });

  test("says when no run of the repository is recorded", async () => {
    // GIVEN
    getRepositoryActivityMock.mockResolvedValue(generateActivity());

    // WHEN
    const component = await render(<RepositoryActivityCard repositoryId="repository-1" />);

    // THEN
    await expect.element(component.getByText("No run recorded")).toBeVisible();
    await expect.element(component.getByText("No finished run recorded")).toBeVisible();
  });

  test("admits a failed check instead of showing the repository as idle", async () => {
    // GIVEN
    getRepositoryActivityMock.mockRejectedValue(new Error("Offline"));

    // WHEN
    const component = await render(<RepositoryActivityCard repositoryId="repository-1" />);

    // THEN
    await expect.element(component.getByText(ACTIVITY_LOAD_FAILED)).toBeVisible();
    await expect.element(component.getByText("No activity")).not.toBeInTheDocument();
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
    await expect.element(component.getByText("1m 04s")).toBeVisible();

    // WHEN
    vi.advanceTimersByTime(2000);

    // THEN
    await expect.element(component.getByText("1m 06s")).toBeVisible();
  });
});
