import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import { BranchesDataTable } from "@/entities/branches/ui/branches-table/branches-data-table";
import { getBranchTableColumns } from "@/entities/branches/ui/branches-table/get-branch-table-columns";
import { useObjectsCount } from "@/entities/nodes/object/ui/queries/get-objects-count.query";
import { useGetProposedChanges } from "@/entities/proposed-changes/ui/queries/get-proposed-changes.query";
import type { BranchRepositoriesResult } from "@/entities/repository/domain/model/branch-repository";
import { useGetBranchRepositories } from "@/entities/repository/ui/queries/get-branch-repositories.query";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

import { render } from "../../../../../tests/components/render";
import { initPointerTracking } from "../../../../../tests/components/utils";
import { generateBranch } from "../../../../../tests/fake/branch";
import {
  generateBranchRepositoriesResult,
  generateBranchRepository,
  SYNC_STATUS,
} from "../../../../../tests/fake/branch-repositories";

vi.mock("@/entities/authentication/ui/auth-provider");
vi.mock("@/entities/proposed-changes/ui/queries/get-proposed-changes.query");
vi.mock("@/entities/schema/ui/hooks/useSchema");
vi.mock("@/entities/nodes/object/ui/queries/get-objects-count.query");
vi.mock("@/entities/repository/ui/queries/get-branch-repositories.query");

const SYNC_STATUS_NO_COLOUR = { value: "mystery", label: null, color: null, description: null };
const FAILING_COMMIT = "1234567890abcdef1234567890abcdef12345678";
const LOAD_ERROR_MESSAGE = "Repository query timed out";

const feature = generateBranch({ id: "branch-feature", name: "feature", sync_with_git: true });

const threeRepositories = generateBranchRepositoriesResult([
  generateBranchRepository({ id: "repo-a", name: "alpha-repo", commit: "8f3c2a1" }),
  generateBranchRepository({
    id: "repo-b",
    name: "beta-repo",
    commit: FAILING_COMMIT,
    syncStatus: SYNC_STATUS.importError,
  }),
  generateBranchRepository({ id: "repo-c", name: "gamma-repo", commit: "61ba9c3" }),
]);

type QueryState = { data: BranchRepositoriesResult } | { pending: true } | { error: Error };

const mockRepositories = (state: QueryState) => {
  vi.mocked(useGetBranchRepositories).mockReturnValue({
    data: "data" in state ? state.data : undefined,
    isPending: "pending" in state,
    isError: "error" in state,
    error: "error" in state ? state.error : null,
  } as unknown as ReturnType<typeof useGetBranchRepositories>);
};

const renderTable = (branches: BranchListItem[] = [feature]) =>
  render(
    <BranchesDataTable
      columns={getBranchTableColumns()}
      data={branches}
      data-testid="branches-table"
    />
  );

const gridChildren = (container: HTMLElement) => [
  ...(container.querySelector('[data-testid="branches-table"]')?.children ?? []),
];

const headerLabels = (container: HTMLElement) =>
  gridChildren(container)
    .slice(0, getBranchTableColumns().length)
    .map((header) => header.textContent?.trim());

const cellOf = (container: HTMLElement, label: string, rowIndex = 0) => {
  const columnCount = getBranchTableColumns().length;
  const columnIndex = headerLabels(container).indexOf(label);
  return gridChildren(container)[columnCount * (rowIndex + 1) + columnIndex];
};

describe("getBranchTableColumns", () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue({
      accessToken: "token",
      isAuthenticated: true,
      setToken: vi.fn(),
      user: null,
    } as unknown as ReturnType<typeof useAuth>);
    vi.mocked(useSchema).mockReturnValue({ schema: null } as unknown as ReturnType<
      typeof useSchema
    >);
    vi.mocked(useGetProposedChanges).mockReturnValue({
      data: undefined,
      isPending: false,
    } as unknown as ReturnType<typeof useGetProposedChanges>);
    vi.mocked(useObjectsCount).mockReturnValue({
      data: 0,
      isLoading: false,
    } as unknown as ReturnType<typeof useObjectsCount>);
    mockRepositories({ data: threeRepositories });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("places Repositories and Git state after Proposed Changes, with no filter or sort control", async () => {
    // WHEN
    const component = await renderTable();

    // THEN
    await expect.element(component.getByText("Repositories", { exact: true })).toBeVisible();
    const labels = headerLabels(component.container);
    const start = labels.indexOf("Proposed Changes");
    expect(labels.slice(start, start + 3)).toEqual([
      "Proposed Changes",
      "Repositories",
      "Git state",
    ]);
    expect(labels).not.toContain("Commit");
    const headers = gridChildren(component.container);
    for (const label of ["Repositories", "Git state"]) {
      expect(headers[labels.indexOf(label)]?.querySelector("button, [role='button']")).toBeNull();
    }
  });

  test("shows the failing repository first, linked on the row's branch", async () => {
    // WHEN
    const component = await renderTable();

    // THEN
    const link = component.getByRole("link", { name: "beta-repo" });
    await expect.element(link).toBeVisible();
    const href = new URL(link.element().getAttribute("href") ?? "", window.location.origin);
    expect(href.pathname).toContain("repo-b");
    expect(href.searchParams.get("branch")).toBe("feature");
    expect(component.getByRole("link", { name: "alpha-repo" }).query()).toBeNull();
  });

  test("adds no branch parameter to the repository link on the default branch's row", async () => {
    // WHEN
    const component = await renderTable([
      generateBranch({ id: "branch-main", name: "main", is_default: true }),
    ]);

    // THEN
    const link = component.getByRole("link", { name: "beta-repo" });
    await expect.element(link).toBeVisible();
    const href = new URL(link.element().getAttribute("href") ?? "", window.location.origin);
    expect(href.searchParams.has("branch")).toBe(false);
  });

  test("shows the Git state label and the short commit in the repository pill's tooltip", async () => {
    // GIVEN
    const component = await renderTable();
    await initPointerTracking(component.locator);

    // WHEN
    await component.getByRole("link", { name: "beta-repo" }).hover();

    // THEN
    await expect
      .element(component.getByRole("tooltip", { name: "Import Error · 1234567" }))
      .toBeVisible();
  });

  test("leaves the commit out of the tooltip when it is null and marks read-only", async () => {
    // GIVEN
    mockRepositories({
      data: generateBranchRepositoriesResult([
        generateBranchRepository({ name: "golden-configs", commit: null, isReadOnly: true }),
      ]),
    });
    const component = await renderTable();
    await initPointerTracking(component.locator);

    // WHEN
    await component.getByRole("link", { name: "golden-configs" }).hover();

    // THEN
    await expect
      .element(component.getByRole("tooltip", { name: "In Sync · read-only" }))
      .toBeVisible();
  });

  test("links +2 more to the branch details page", async () => {
    // WHEN
    const component = await renderTable();

    // THEN
    const more = component.getByRole("link", { name: "+2 more" });
    await expect.element(more).toBeVisible();
    expect(more.element().getAttribute("href")).toBe("/branches/feature");
  });

  test("shows the worst Git state in the schema colour with its share and per-label counts", async () => {
    // GIVEN
    const component = await renderTable();
    await initPointerTracking(component.locator);

    // WHEN
    await component.getByText("1/3", { exact: true }).hover();

    // THEN
    await expect
      .element(component.getByText("Import Error", { exact: true }))
      .toHaveStyle({ backgroundColor: "rgb(248, 113, 113)" });
    await expect
      .element(component.getByRole("tooltip", { name: "Import Error: 1 · In Sync: 2" }))
      .toBeVisible();
  });

  test("shows no count and no +more for a single repository", async () => {
    // GIVEN
    mockRepositories({ data: generateBranchRepositoriesResult([generateBranchRepository()]) });

    // WHEN
    const component = await renderTable();

    // THEN
    await expect.element(component.getByText("In Sync", { exact: true })).toBeVisible();
    expect(cellOf(component.container, "Git state")?.textContent).toBe("In Sync");
    expect(component.getByRole("link", { name: /more/ }).query()).toBeNull();
  });

  test("shows a grey badge with the raw value when the status has no colour", async () => {
    // GIVEN
    mockRepositories({
      data: generateBranchRepositoriesResult([
        generateBranchRepository({ syncStatus: SYNC_STATUS_NO_COLOUR }),
      ]),
    });

    // WHEN
    const component = await renderTable();

    // THEN
    const badge = component.getByText("mystery", { exact: true });
    await expect.element(badge).toBeVisible();
    expect(badge.element().getAttribute("style")).toBeNull();
  });

  test("shows one spinner in the Repositories cell and a blank Git state while pending", async () => {
    // GIVEN
    mockRepositories({ pending: true });

    // WHEN
    const component = await renderTable();

    // THEN
    await expect.element(component.getByRole("status")).toBeVisible();
    expect(component.getByRole("status").elements()).toHaveLength(1);
    const { container } = component;
    expect(cellOf(container, "Repositories")?.querySelector("[role='status']")).not.toBeNull();
    expect(cellOf(container, "Git state")?.textContent).toBe("");
  });

  test.each([
    {
      name: "empty, not synced",
      state: { data: generateBranchRepositoriesResult([]) },
      branch: { sync_with_git: false },
      text: "Not synced with Git",
    },
    {
      name: "empty, synced",
      state: { data: generateBranchRepositoriesResult([]) },
      branch: { sync_with_git: true },
      text: "No repositories",
    },
    {
      name: "denied",
      state: { data: { status: "denied" } as BranchRepositoriesResult },
      text: "No permission",
    },
    {
      name: "error",
      state: { error: new Error(LOAD_ERROR_MESSAGE) },
      text: "Could not load repositories",
      cellText: `Could not load repositories${LOAD_ERROR_MESSAGE}`,
    },
  ])(
    "reads $text when $name, with a blank Git state",
    async ({ state, branch = {}, text, cellText = text }) => {
      // GIVEN
      mockRepositories(state as QueryState);

      // WHEN
      const component = await renderTable([{ ...feature, ...branch }]);

      // THEN
      const label = component.getByText(text, { exact: true });
      await expect.element(label).toBeVisible();
      await expect.element(label).toHaveClass("text-foreground-muted");
      await expect.element(component.getByRole("link", { name: "feature" })).toBeVisible();
      const { container } = component;
      expect(cellOf(container, "Repositories")?.textContent).toBe(cellText);
      expect(cellOf(container, "Git state")?.textContent).toBe("");
    }
  );

  test("shows the load error's message on hover and to assistive technology", async () => {
    // GIVEN
    mockRepositories({ error: new Error(LOAD_ERROR_MESSAGE) });
    const component = await renderTable();
    await initPointerTracking(component.locator);

    // WHEN
    await component.getByText("Could not load repositories", { exact: true }).hover();

    // THEN
    await expect
      .element(component.getByRole("tooltip", { name: LOAD_ERROR_MESSAGE }))
      .toBeVisible();
    const reason = cellOf(component.container, "Repositories")?.querySelector(".sr-only");
    expect(reason?.textContent).toBe(LOAD_ERROR_MESSAGE);
  });

  test("labels the row checkbox with the branch name", async () => {
    // WHEN
    const component = await renderTable();

    // THEN
    await expect.element(component.getByRole("checkbox", { name: "Select feature" })).toBeVisible();
  });
});
