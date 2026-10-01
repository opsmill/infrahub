import { afterEach, describe, expect, test, vi } from "vitest";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getObjectsCountFromApi } from "@/entities/nodes/object/api/get-objects-count-from-api";
import {
  GENERIC_REPOSITORY_KIND,
  REPOSITORY_ERROR_IMPORT_FILTER,
} from "@/entities/repository/domain/model/repository";
import { RepositorySyncStatus } from "@/entities/repository/ui/repository-sync-status";

import { render } from "../../../../tests/components/render";
import { initPointerTracking } from "../../../../tests/components/utils";
import { generateBranch } from "../../../../tests/fake/branch";

vi.mock("@/entities/branches/ui/branches-provider");
vi.mock("@/entities/nodes/object/api/get-objects-count-from-api");

type CountResponse = Awaited<ReturnType<typeof getObjectsCountFromApi>>;

const countResponse = (count: number) =>
  ({ data: { [GENERIC_REPOSITORY_KIND]: { count } } }) as unknown as CountResponse;

const errorResponse = () =>
  ({ data: null, errors: [{ message: "boom" }] }) as unknown as CountResponse;

const FAILING_LABEL = "Repositories failed to import on this branch";
const IN_SYNC_LABEL = "All Git repositories are in sync on this branch";
const NO_REPOSITORIES_LABEL = "No Git repositories";
const CHECK_FAILED_LABEL = "Git repository sync status could not be checked";

describe("RepositorySyncStatus", () => {
  const useCurrentBranchMock = vi.mocked(useCurrentBranch);
  const getObjectsCountFromApiMock = vi.mocked(getObjectsCountFromApi);

  /** The two counts are told apart by their filter, never by call order. */
  const mockCounts = ({
    total,
    failing,
  }: {
    total: number | "error";
    failing: number | "error";
  }) => {
    getObjectsCountFromApiMock.mockImplementation(async ({ filters }) => {
      const isFailingLookup = filters?.some(
        (filter) =>
          filter.name === REPOSITORY_ERROR_IMPORT_FILTER.name &&
          filter.value === REPOSITORY_ERROR_IMPORT_FILTER.value
      );
      const outcome = isFailingLookup ? failing : total;
      return outcome === "error" ? errorResponse() : countResponse(outcome);
    });
  };

  const mockNeverSettles = () => {
    getObjectsCountFromApiMock.mockImplementation(() => new Promise(() => {}));
  };

  const onBranch = (overrides: Parameters<typeof generateBranch>[0] = {}) => {
    const branch = generateBranch(overrides);
    useCurrentBranchMock.mockReturnValue({ currentBranch: branch, setCurrentBranch: () => {} });
    return branch;
  };

  const glyphIcon = (component: { container: HTMLElement }) =>
    component.container
      .querySelector('[data-testid="repository-sync-status-glyph"]')
      ?.firstElementChild?.getAttribute("icon");

  const hrefOf = async (component: Awaited<ReturnType<typeof render>>) =>
    (await component.getByTestId("repository-sync-status").element()).getAttribute("href") ?? "";

  afterEach(() => {
    vi.resetAllMocks();
    vi.useRealTimers();
    window.history.pushState({}, "", "/");
  });

  test("renders the failing appearance with a pulsing dot when a repository is failing", async () => {
    // GIVEN
    onBranch({ name: "branch1" });
    mockCounts({ total: 3, failing: 1 });

    // WHEN
    const component = await render(<RepositorySyncStatus />);

    // THEN
    await expect.element(component.getByRole("link", { name: FAILING_LABEL })).toBeVisible();
    await expect.element(component.getByTestId("repository-sync-status-pulse")).toBeVisible();
    expect(glyphIcon(component)).toBe("mdi:source-branch");
  });

  test("renders the in-sync appearance with no pulsing dot when repositories are healthy", async () => {
    // GIVEN
    onBranch({ name: "branch1" });
    mockCounts({ total: 3, failing: 0 });

    // WHEN
    const component = await render(<RepositorySyncStatus />);

    // THEN
    await expect.element(component.getByRole("link", { name: IN_SYNC_LABEL })).toBeVisible();
    expect(
      component.container.querySelector('[data-testid="repository-sync-status-pulse"]')
    ).toBeNull();
    expect(glyphIcon(component)).toBe("mdi:source-branch");
  });

  test("treats a syncing repository as in-sync rather than giving it its own treatment", async () => {
    // GIVEN repositories that are syncing rather than failing
    onBranch({ name: "branch1" });
    mockCounts({ total: 2, failing: 0 });

    // WHEN
    const component = await render(<RepositorySyncStatus />);

    // THEN
    await expect.element(component.getByRole("link", { name: IN_SYNC_LABEL })).toBeVisible();
  });

  test("stays a link, dimmed, when no repositories are configured", async () => {
    // GIVEN
    onBranch({ name: "branch1" });
    mockCounts({ total: 0, failing: 0 });

    // WHEN
    const component = await render(<RepositorySyncStatus />);

    // THEN it is reachable rather than disabled: the repository list is still where you go
    const indicator = component.getByRole("link", { name: NO_REPOSITORIES_LABEL });
    await expect.element(indicator).toBeVisible();
    await expect.element(indicator).not.toHaveAttribute("data-disabled");
    await expect.element(indicator).not.toHaveAttribute("aria-disabled");
    await expect.element(indicator).toHaveAttribute("href");
    expect((await indicator.element()).className).toContain("opacity-60");
  });

  test.each([
    ["failing", { total: 3, failing: 1 } as const],
    ["in-sync", { total: 3, failing: 0 } as const],
    ["no-repositories", { total: 0, failing: 0 } as const],
  ])("stays an enabled link with somewhere to go in the %s state", async (_label, counts) => {
    // GIVEN
    onBranch({ name: "branch1" });
    mockCounts(counts);

    // WHEN
    const component = await render(<RepositorySyncStatus />);

    // THEN
    const indicator = component.getByTestId("repository-sync-status");
    await expect.element(indicator).toBeVisible();
    await expect.element(indicator).not.toHaveAttribute("data-disabled");
    expect((await indicator.element()).getAttribute("href")).toContain(
      `/objects/${GENERIC_REPOSITORY_KIND}`
    );
  });

  test("still explains itself on hover when no repositories are configured", async () => {
    // GIVEN
    onBranch({ name: "branch1" });
    mockCounts({ total: 0, failing: 0 });

    // WHEN
    const component = await render(<RepositorySyncStatus />);
    const indicator = component.getByRole("link", { name: NO_REPOSITORIES_LABEL });
    await expect.element(indicator).toBeVisible();
    await initPointerTracking(component.locator);
    await indicator.hover();

    // THEN
    await expect
      .element(component.getByRole("tooltip", { name: NO_REPOSITORIES_LABEL }))
      .toBeVisible();
    await initPointerTracking(component.locator);
  });

  test("renders the check-failed appearance when a lookup fails", async () => {
    // GIVEN
    onBranch({ name: "branch1" });
    mockCounts({ total: "error", failing: "error" });

    // WHEN
    const component = await render(<RepositorySyncStatus />);

    // THEN
    await expect.element(component.getByRole("link", { name: CHECK_FAILED_LABEL })).toBeVisible();
    expect(glyphIcon(component)).toBe("mdi:error-outline");
    const glyph = component.container.querySelector(
      '[data-testid="repository-sync-status-glyph"]'
    )?.firstElementChild;
    expect(glyph?.className).toContain("text-foreground-muted");
    expect(glyph?.className).not.toContain("text-danger");
  });

  test("reports no repositories, not check-failed, when the branch is empty and the failure lookup fails", async () => {
    // GIVEN
    onBranch({ name: "branch1" });
    mockCounts({ total: 0, failing: "error" });

    // WHEN
    const component = await render(<RepositorySyncStatus />);

    // THEN
    await expect
      .element(component.getByRole("link", { name: NO_REPOSITORIES_LABEL }))
      .toBeVisible();
  });

  test("shows a loading treatment, holding its place, until the first lookup settles", async () => {
    // GIVEN
    onBranch({ name: "branch1" });
    mockNeverSettles();

    // WHEN
    const component = await render(<RepositorySyncStatus />);

    // THEN
    await expect
      .element(component.getByRole("link", { name: "Checking Git repository sync status" }))
      .toBeVisible();
    const slot = component.container.querySelector('[data-testid="repository-sync-status-glyph"]');
    expect(slot?.className).toContain("size-4");
  });

  test("filters the destination to failures only while something is failing", async () => {
    // GIVEN
    onBranch({ name: "branch1", is_default: false });
    mockCounts({ total: 3, failing: 1 });

    // WHEN
    const component = await render(<RepositorySyncStatus />);
    await expect.element(component.getByRole("link", { name: FAILING_LABEL })).toBeVisible();

    // THEN
    const href = await hrefOf(component);
    expect(href).toContain(`/objects/${GENERIC_REPOSITORY_KIND}`);
    expect(decodeURIComponent(href)).toContain("sync_status__value");
    expect(decodeURIComponent(href)).toContain("error-import");
  });

  test("leaves the destination unfiltered when nothing is failing", async () => {
    // GIVEN
    onBranch({ name: "branch1", is_default: false });
    mockCounts({ total: 3, failing: 0 });

    // WHEN
    const component = await render(<RepositorySyncStatus />);
    await expect.element(component.getByRole("link", { name: IN_SYNC_LABEL })).toBeVisible();

    // THEN the list is not narrowed to an error that is not there, which would render empty
    expect(decodeURIComponent(await hrefOf(component))).not.toContain("error-import");
  });

  test("leaves the destination unfiltered when no repositories are configured", async () => {
    // GIVEN
    onBranch({ name: "branch1", is_default: false });
    mockCounts({ total: 0, failing: 0 });

    // WHEN
    const component = await render(<RepositorySyncStatus />);
    await expect
      .element(component.getByRole("link", { name: NO_REPOSITORIES_LABEL }))
      .toBeVisible();

    // THEN
    expect(decodeURIComponent(await hrefOf(component))).not.toContain("error-import");
  });

  test("includes the branch in the link when the branch is not the default", async () => {
    // GIVEN
    onBranch({ name: "branch1", is_default: false });
    mockCounts({ total: 3, failing: 1 });

    // WHEN
    const component = await render(<RepositorySyncStatus />);
    await expect.element(component.getByRole("link", { name: FAILING_LABEL })).toBeVisible();

    // THEN
    expect(decodeURIComponent(await hrefOf(component))).toContain("branch1");
  });

  test("omits the branch from the link on the default branch", async () => {
    // GIVEN
    onBranch({ name: "main", is_default: true });
    mockCounts({ total: 3, failing: 1 });

    // WHEN
    const component = await render(<RepositorySyncStatus />);
    await expect.element(component.getByRole("link", { name: FAILING_LABEL })).toBeVisible();

    // THEN
    expect(await hrefOf(component)).not.toContain("branch=");
  });

  test("asks about the branch from context, not a branch named in the URL", async () => {
    // GIVEN a different branch in the URL
    onBranch({ name: "branch1", is_default: false });
    mockCounts({ total: 3, failing: 1 });
    window.history.pushState({}, "", "/?branch=some-other-branch");

    // WHEN
    await render(<RepositorySyncStatus />);

    // THEN
    expect(getObjectsCountFromApiMock).toHaveBeenCalledTimes(2);
    for (const call of getObjectsCountFromApiMock.mock.calls) {
      expect(call[0].branchName).toBe("branch1");
    }
  });

  test("asks about now, ignoring the header time frame", async () => {
    // GIVEN
    onBranch({ name: "branch1" });
    mockCounts({ total: 3, failing: 0 });

    // WHEN
    await render(<RepositorySyncStatus />);

    // THEN
    expect(getObjectsCountFromApiMock).toHaveBeenCalledTimes(2);
    for (const call of getObjectsCountFromApiMock.mock.calls) {
      expect(call[0].atDate).toBeNull();
    }
  });

  test("does not carry a time-frame selection into the link", async () => {
    // GIVEN a page already scoped to a past moment
    onBranch({ name: "branch1", is_default: false });
    mockCounts({ total: 3, failing: 1 });
    window.history.pushState({}, "", "/?at=2020-01-01T00%3A00%3A00.000Z");

    // WHEN
    const component = await render(<RepositorySyncStatus />);
    await expect.element(component.getByRole("link", { name: FAILING_LABEL })).toBeVisible();

    // THEN
    expect(await hrefOf(component)).not.toContain("at=");
  });

  test("counts every repository kind through the generic kind", async () => {
    // GIVEN
    onBranch({ name: "branch1" });
    mockCounts({ total: 3, failing: 0 });

    // WHEN
    await render(<RepositorySyncStatus />);

    // THEN
    expect(getObjectsCountFromApiMock).toHaveBeenCalledTimes(2);
    for (const call of getObjectsCountFromApiMock.mock.calls) {
      expect(call[0].objectKind).toBe(GENERIC_REPOSITORY_KIND);
    }
  });

  test("keeps a resolved state when the refresh interval fires", async () => {
    // GIVEN
    vi.useFakeTimers({ shouldAdvanceTime: true });
    onBranch({ name: "branch1" });
    mockCounts({ total: 3, failing: 1 });
    const component = await render(<RepositorySyncStatus />);
    const indicator = component.getByRole("link", { name: FAILING_LABEL });
    await expect.element(indicator).toBeVisible();
    const callsBefore = getObjectsCountFromApiMock.mock.calls.length;

    // WHEN
    await vi.advanceTimersByTimeAsync(10_000);

    // THEN the lookups ran again and the resolved state stayed put
    expect(getObjectsCountFromApiMock.mock.calls.length).toBeGreaterThan(callsBefore);
    await expect.element(indicator).toBeVisible();
  });

  test("drops a stale failure when a background refresh stops being able to check", async () => {
    // GIVEN a resolved failing state
    vi.useFakeTimers({ shouldAdvanceTime: true });
    onBranch({ name: "branch1", is_default: false });
    mockCounts({ total: 3, failing: 1 });
    const component = await render(<RepositorySyncStatus />);
    await expect.element(component.getByRole("link", { name: FAILING_LABEL })).toBeVisible();

    // WHEN the refresh can no longer reach the counts
    mockCounts({ total: "error", failing: "error" });
    await vi.advanceTimersByTimeAsync(10_000);

    // THEN no alarm is left pulsing on a reading that can no longer be refreshed
    await expect.element(component.getByRole("link", { name: CHECK_FAILED_LABEL })).toBeVisible();
    expect(
      component.container.querySelector('[data-testid="repository-sync-status-pulse"]')
    ).toBeNull();
    expect(decodeURIComponent(await hrefOf(component))).not.toContain("error-import");
  });

  test.each([
    ["failing", { total: 3, failing: 1 } as const, FAILING_LABEL],
    ["in-sync", { total: 3, failing: 0 } as const, IN_SYNC_LABEL],
    ["no-repositories", { total: 0, failing: 0 } as const, NO_REPOSITORIES_LABEL],
  ])("names the %s state exactly", async (_label, counts, name) => {
    // GIVEN
    onBranch({ name: "branch1" });
    mockCounts(counts);

    // WHEN
    const component = await render(<RepositorySyncStatus />);

    // THEN the name is pinned: the e2e suite locates the branch selector by accessible-name
    // substring, so an unexpected name here can collide with it
    await expect.element(component.getByRole("link", { name })).toBeVisible();
  });
});
