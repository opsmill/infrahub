import { afterEach, describe, expect, test, vi } from "vitest";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getObjectsCountFromApi } from "@/entities/nodes/object/api/get-objects-count-from-api";
import {
  GENERIC_REPOSITORY_KIND,
  REPOSITORY_ERROR_IMPORT_FILTER,
} from "@/entities/repository/domain/model/repository";
import { GitStatus } from "@/entities/repository/ui/git-status";

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

describe("GitStatus", () => {
  const useCurrentBranchMock = vi.mocked(useCurrentBranch);
  const getObjectsCountFromApiMock = vi.mocked(getObjectsCountFromApi);

  /**
   * Both counts go through the same API function, so they are told apart by whether the call
   * carries the sync-status filter — never by call order, which is an implementation detail a
   * later refactor would silently invalidate.
   */
  const mockCounts = ({
    total,
    failing,
  }: {
    total: number | "error";
    failing: number | "error";
  }) => {
    getObjectsCountFromApiMock.mockImplementation(async ({ filters }) => {
      // Keyed off the real constant: if the component ever stops passing this filter, the
      // mock misclassifies loudly rather than quietly returning the wrong count.
      const isFailingLookup = filters?.some(
        (filter) =>
          filter.name === REPOSITORY_ERROR_IMPORT_FILTER.name &&
          filter.value === REPOSITORY_ERROR_IMPORT_FILTER.value
      );
      const outcome = isFailingLookup ? failing : total;
      return outcome === "error" ? errorResponse() : countResponse(outcome);
    });
  };

  const glyphIcon = (component: { container: HTMLElement }) =>
    component.container
      .querySelector('[data-testid="git-status-glyph"]')
      ?.firstElementChild?.getAttribute("icon");

  /** Leaves a lookup permanently in flight so the loading state can actually be rendered. */
  const mockNeverSettles = () => {
    getObjectsCountFromApiMock.mockImplementation(() => new Promise(() => {}));
  };

  const onBranch = (overrides: Parameters<typeof generateBranch>[0] = {}) => {
    const branch = generateBranch(overrides);
    useCurrentBranchMock.mockReturnValue({ currentBranch: branch, setCurrentBranch: () => {} });
    return branch;
  };

  afterEach(() => {
    vi.resetAllMocks();
    // Restored here, not at the end of the test that sets it: an assertion throwing midway
    // would otherwise leak the URL into every later test in this file.
    window.history.pushState({}, "", "/");
  });

  test("renders the error appearance with a pulsing dot when a repository is failing", async () => {
    // GIVEN
    onBranch({ name: "branch1" });
    mockCounts({ total: 3, failing: 1 });

    // WHEN
    const component = await render(<GitStatus />);

    // THEN
    const indicator = component.getByRole("link", {
      name: "Repositories failed to import on this branch",
    });
    await expect.element(indicator).toBeVisible();
    await expect.element(component.getByTestId("git-status-pulse")).toBeVisible();
    // Same subject glyph as every other resolved state: the state is carried by colour and
    // the dot, never by swapping the icon for a different subject.
    expect(glyphIcon(component)).toBe("mdi:source-branch");
  });

  test("renders the neutral appearance with no pulsing dot when repositories are healthy", async () => {
    // GIVEN
    onBranch({ name: "branch1" });
    mockCounts({ total: 3, failing: 0 });

    // WHEN
    const component = await render(<GitStatus />);

    // THEN
    const indicator = component.getByRole("link", {
      name: "All Git repositories are in sync on this branch",
    });
    await expect.element(indicator).toBeVisible();
    expect(component.container.querySelector('[data-testid="git-status-pulse"]')).toBeNull();
    // The dot, not the glyph, is what distinguishes this from the error state — so the two
    // remain distinguishable without perceiving colour.
    expect(glyphIcon(component)).toBe("mdi:source-branch");
  });

  test("treats a syncing repository as neutral rather than giving it its own treatment", async () => {
    // GIVEN a branch whose repositories are mid-sync: none carries the import-error status,
    // so the failing count is zero even though the repositories are not idle
    onBranch({ name: "branch1" });
    mockCounts({ total: 2, failing: 0 });

    // WHEN
    const component = await render(<GitStatus />);

    // THEN
    await expect
      .element(
        component.getByRole("link", { name: "All Git repositories are in sync on this branch" })
      )
      .toBeVisible();
  });

  test("renders inert and not activatable when the branch has no repositories", async () => {
    // GIVEN
    onBranch({ name: "branch1" });
    mockCounts({ total: 0, failing: 0 });

    // WHEN
    const component = await render(<GitStatus />);

    // THEN it is a button, not a link: with no repositories there is nowhere to navigate to
    const indicator = component.getByRole("button", {
      name: "No Git repositories configured",
    });
    await expect.element(indicator).toBeVisible();
    expect((await indicator.element()).getAttribute("href")).toBeNull();
    expect(glyphIcon(component)).toBe("mdi:source-branch");
  });

  test("still explains itself on hover while inert", async () => {
    // GIVEN a branch with no repositories, so the control is disabled
    onBranch({ name: "branch1" });
    mockCounts({ total: 0, failing: 0 });

    // WHEN the operator hovers the inert control
    const component = await render(<GitStatus />);
    const indicator = component.getByRole("button", { name: "No Git repositories configured" });
    await expect.element(indicator).toBeVisible();
    await initPointerTracking(component.locator);
    await indicator.hover();

    // THEN the tooltip still fires. No other call site in this codebase combines LinkButton
    // An inactive control still has to say why it is inactive, so the tooltip is asserted
    // rather than assumed.
    await expect
      .element(component.getByRole("tooltip", { name: "No Git repositories configured" }))
      .toBeVisible();
    // Move the pointer away so the open overlay cannot leak into a later test.
    await initPointerTracking(component.locator);
  });

  test("renders the check-failed appearance when a lookup fails", async () => {
    // GIVEN
    onBranch({ name: "branch1" });
    mockCounts({ total: "error", failing: "error" });

    // WHEN
    const component = await render(<GitStatus />);

    // THEN
    await expect
      .element(component.getByRole("link", { name: "Git status could not be checked" }))
      .toBeVisible();
    expect(glyphIcon(component)).toBe("mdi:error-outline");
    // Muted, never danger. An operator without permission to read repositories fails this
    // lookup on every page, so a red alarm here would be permanent and unclearable — the
    // regression this assertion exists to catch.
    const glyph = component.container.querySelector(
      '[data-testid="git-status-glyph"]'
    )?.firstElementChild;
    expect(glyph?.className).toContain("text-foreground-muted");
    expect(glyph?.className).not.toContain("text-danger");
  });

  test("shows a loading treatment, holding its place, until the first lookup settles", async () => {
    // GIVEN a lookup that never settles
    onBranch({ name: "branch1" });
    mockNeverSettles();

    // WHEN
    const component = await render(<GitStatus />);

    // THEN it neither claims health nor claims failure, and the slot is already sized
    await expect
      .element(component.getByRole("link", { name: "Checking Git status" }))
      .toBeVisible();
    const slot = component.container.querySelector('[data-testid="git-status-glyph"]');
    expect(slot?.className).toContain("size-4");
    expect(component.container.querySelector('[data-testid="git-status-pulse"]')).toBeNull();
  });

  test("reports inert, not check-failed, when the branch is empty and the failure lookup fails", async () => {
    // GIVEN a branch with no repositories, so the failing count cannot change the answer
    onBranch({ name: "branch1" });
    mockCounts({ total: 0, failing: "error" });

    // WHEN
    const component = await render(<GitStatus />);

    // THEN
    await expect
      .element(component.getByRole("button", { name: "No Git repositories configured" }))
      .toBeVisible();
  });

  test("keeps the glyph slot the same size in every state", async () => {
    // GIVEN
    onBranch({ name: "branch1" });
    mockCounts({ total: 3, failing: 1 });

    // WHEN
    const component = await render(<GitStatus />);

    // THEN the slot is pinned rather than sized by whichever glyph occupies it, so the header
    // cannot shift when the state changes
    const slot = component.container.querySelector('[data-testid="git-status-glyph"]');
    expect(slot?.className).toContain("size-4");
  });

  test("links to the repository list filtered to failed imports", async () => {
    // GIVEN
    onBranch({ name: "branch1", is_default: false });
    mockCounts({ total: 3, failing: 1 });

    // WHEN
    const component = await render(<GitStatus />);

    // THEN
    const indicator = component.getByRole("link", {
      name: "Repositories failed to import on this branch",
    });
    // Wait for the error state to resolve before reading the href: `.element()` resolves
    // immediately, so without this it reads the loading state's markup.
    await expect.element(indicator).toBeVisible();
    const href = (await indicator.element()).getAttribute("href") ?? "";
    expect(href).toContain(`/objects/${GENERIC_REPOSITORY_KIND}`);
    expect(decodeURIComponent(href)).toContain("sync_status__value");
    expect(decodeURIComponent(href)).toContain("error-import");
  });

  test("includes the branch in the link when the branch is not the default", async () => {
    // GIVEN
    onBranch({ name: "branch1", is_default: false });
    mockCounts({ total: 3, failing: 1 });

    // WHEN
    const component = await render(<GitStatus />);

    // THEN
    const indicator = component.getByRole("link", {
      name: "Repositories failed to import on this branch",
    });
    await expect.element(indicator).toBeVisible();
    expect(decodeURIComponent((await indicator.element()).getAttribute("href") ?? "")).toContain(
      "branch1"
    );
  });

  test("omits the branch from the link on the default branch", async () => {
    // GIVEN
    onBranch({ name: "main", is_default: true });
    mockCounts({ total: 3, failing: 1 });

    // WHEN
    const component = await render(<GitStatus />);

    // THEN
    const indicator = component.getByRole("link", {
      name: "Repositories failed to import on this branch",
    });
    await expect.element(indicator).toBeVisible();
    expect((await indicator.element()).getAttribute("href") ?? "").not.toContain("branch=");
  });

  test("asks about the branch from context, not a branch named in the URL", async () => {
    // GIVEN the URL names a different branch from the one selected in the application
    onBranch({ name: "branch1", is_default: false });
    mockCounts({ total: 3, failing: 1 });
    window.history.pushState({}, "", "/?branch=some-other-branch");

    // WHEN
    await render(<GitStatus />);

    // THEN both lookups are scoped to the branch from context
    expect(getObjectsCountFromApiMock).toHaveBeenCalledTimes(2);
    for (const call of getObjectsCountFromApiMock.mock.calls) {
      expect(call[0].branchName).toBe("branch1");
    }
  });

  test("does not carry a time-frame selection into the link", async () => {
    // GIVEN a page already scoped to a past moment
    onBranch({ name: "branch1", is_default: false });
    mockCounts({ total: 3, failing: 1 });
    window.history.pushState({}, "", "/?at=2020-01-01T00%3A00%3A00.000Z");

    // WHEN
    const component = await render(<GitStatus />);

    // THEN the destination is present-time, like the indicator: a historical list could omit
    // the very repository that is failing now.
    const indicator = component.getByRole("link", {
      name: "Repositories failed to import on this branch",
    });
    await expect.element(indicator).toBeVisible();
    expect((await indicator.element()).getAttribute("href") ?? "").not.toContain("at=");
  });

  test("asks about now, ignoring the header time machine", async () => {
    // GIVEN
    onBranch({ name: "branch1" });
    mockCounts({ total: 3, failing: 0 });

    // WHEN
    await render(<GitStatus />);

    // THEN the lookups carry no historical date: a past "all clear" would be reported in the
    // present tense, which is the failure this indicator exists to prevent
    expect(getObjectsCountFromApiMock).toHaveBeenCalledTimes(2);
    for (const call of getObjectsCountFromApiMock.mock.calls) {
      expect(call[0].atDate).toBeNull();
    }
  });

  test.each([
    [
      "error",
      { total: 3, failing: 1 } as const,
      "link",
      "Repositories failed to import on this branch",
    ],
    [
      "neutral",
      { total: 3, failing: 0 } as const,
      "link",
      "All Git repositories are in sync on this branch",
    ],
    ["inert", { total: 0, failing: 0 } as const, "button", "No Git repositories configured"],
  ])("names the %s state without the word branch on a button", async (_label, counts, role, name) => {
    // GIVEN
    onBranch({ name: "branch1" });
    mockCounts(counts);

    // WHEN
    const component = await render(<GitStatus />);

    // THEN the control exposes the role and name this state is meant to expose, and no button
    // here can be found by searching accessible names for "branch" — the branch selector is
    // located that way, and a second match breaks it.
    await expect.element(component.getByRole(role, { name })).toBeVisible();
    for (const button of [...component.container.querySelectorAll("button")]) {
      expect(button.getAttribute("aria-label")?.toLowerCase() ?? "").not.toContain("branch");
    }
  });

  test("keeps a resolved state through a background refetch", async () => {
    // GIVEN a resolved error state
    onBranch({ name: "branch1" });
    mockCounts({ total: 3, failing: 1 });
    const component = await render(<GitStatus />);
    await expect
      .element(
        component.getByRole("link", { name: "Repositories failed to import on this branch" })
      )
      .toBeVisible();
    const callsAfterFirstLoad = getObjectsCountFromApiMock.mock.calls.length;

    // WHEN the lookups run again in the background, as the refresh interval makes them do
    await component.rerender(<GitStatus />);

    // THEN the resolved state stays put. Reading the refetching flag rather than the initial
    // pending flag would drop the indicator back to its loading treatment on every poll.
    await expect
      .element(
        component.getByRole("link", { name: "Repositories failed to import on this branch" })
      )
      .toBeVisible();
    expect(getObjectsCountFromApiMock.mock.calls.length).toBeGreaterThanOrEqual(
      callsAfterFirstLoad
    );
  });

  test("counts every repository kind through the generic kind", async () => {
    // GIVEN
    onBranch({ name: "branch1" });
    mockCounts({ total: 3, failing: 0 });

    // WHEN
    await render(<GitStatus />);

    // THEN
    expect(getObjectsCountFromApiMock).toHaveBeenCalledTimes(2);
    for (const call of getObjectsCountFromApiMock.mock.calls) {
      expect(call[0].objectKind).toBe(GENERIC_REPOSITORY_KIND);
    }
  });
});
