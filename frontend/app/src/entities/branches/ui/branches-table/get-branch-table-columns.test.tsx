import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import type { BranchTableRow } from "@/entities/branches/domain/model/branch-table-row";
import { BranchesDataTable } from "@/entities/branches/ui/branches-table/branches-data-table";
import { getBranchTableColumns } from "@/entities/branches/ui/branches-table/get-branch-table-columns";
import { useObjectsCount } from "@/entities/nodes/object/ui/queries/get-objects-count.query";
import { useGetProposedChanges } from "@/entities/proposed-changes/ui/queries/get-proposed-changes.query";
import { READONLY_REPOSITORY_KIND } from "@/entities/repository/domain/model/repository";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

import { render } from "../../../../../tests/components/render";
import { initPointerTracking } from "../../../../../tests/components/utils";
import { OPERATIONAL_STATUS, SYNC_STATUS } from "../../../../../tests/fake/branch-repositories";
import {
  FULL_COMMIT_HASH,
  generateBranchTableRow,
} from "../../../../../tests/fake/branch-table-rows";

vi.mock("@/entities/authentication/ui/auth-provider");
vi.mock("@/entities/proposed-changes/ui/queries/get-proposed-changes.query");
vi.mock("@/entities/schema/ui/hooks/useSchema");
vi.mock("@/entities/nodes/object/ui/queries/get-objects-count.query");

const SYNC_STATUS_NO_COLOUR = {
  value: "mystery",
  label: "Mystery",
  color: null,
  description: null,
};

const featureBranch = { id: "branch-feature", name: "feature", is_default: false };

const renderTable = (rows: BranchTableRow[]) =>
  render(
    <BranchesDataTable columns={getBranchTableColumns()} data={rows} data-testid="branches-table" />
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
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  test("places Repository, Git state and Commit after Proposed Changes, with no filter or sort control", async () => {
    // GIVEN
    const rows = [generateBranchTableRow({ branch: featureBranch })];

    // WHEN
    const component = await renderTable(rows);

    // THEN
    await expect.element(component.getByText("Repository", { exact: true })).toBeVisible();
    const labels = headerLabels(component.container);
    const start = labels.indexOf("Proposed Changes");
    expect(labels.slice(start, start + 4)).toEqual([
      "Proposed Changes",
      "Repository",
      "Git state",
      "Commit",
    ]);
    const headers = gridChildren(component.container);
    for (const label of ["Repository", "Git state", "Commit"]) {
      const header = headers[labels.indexOf(label)];
      expect(header?.querySelector("button, [role='button']")).toBeNull();
    }
  });

  test("links the repository to its page on the row's branch", async () => {
    // GIVEN
    const rows = [generateBranchTableRow({ branch: featureBranch })];

    // WHEN
    const component = await renderTable(rows);

    // THEN
    const link = component.getByRole("link", { name: "infrastructure-templates" });
    await expect.element(link).toBeVisible();
    const href = new URL(link.element().getAttribute("href") ?? "", window.location.origin);
    expect(href.searchParams.get("branch")).toBe("feature");
  });

  test("adds no branch parameter to the repository link on the default branch's row", async () => {
    // GIVEN
    const rows = [
      generateBranchTableRow({ branch: { id: "branch-main", name: "main", is_default: true } }),
    ];

    // WHEN
    const component = await renderTable(rows);

    // THEN
    const link = component.getByRole("link", { name: "infrastructure-templates" });
    await expect.element(link).toBeVisible();
    const href = new URL(link.element().getAttribute("href") ?? "", window.location.origin);
    expect(href.searchParams.has("branch")).toBe(false);
  });

  test("marks a read-only repository", async () => {
    // GIVEN
    const rows = [
      generateBranchTableRow({
        branch: featureBranch,
        repository: { kind: READONLY_REPOSITORY_KIND, isReadOnly: true },
      }),
    ];

    // WHEN
    const component = await renderTable(rows);

    // THEN
    await expect.element(component.getByText("Read-only")).toBeVisible();
  });

  test("shows the Git state pill in the schema colour with its description as tooltip", async () => {
    // GIVEN
    const rows = [
      generateBranchTableRow({
        branch: featureBranch,
        repository: { syncStatus: SYNC_STATUS.importError },
      }),
    ];
    const component = await renderTable(rows);
    await initPointerTracking(component.locator);

    // WHEN
    const pill = component.getByText("Import Error", { exact: true });
    await pill.hover();

    // THEN
    await expect.element(pill).toHaveStyle({ backgroundColor: "rgb(248, 113, 113)" });
    await expect
      .element(component.getByRole("tooltip", { name: SYNC_STATUS.importError.description }))
      .toBeVisible();
  });

  test("shows a grey badge with the raw value when the status has no colour", async () => {
    // GIVEN
    const rows = [
      generateBranchTableRow({
        branch: featureBranch,
        repository: { syncStatus: SYNC_STATUS_NO_COLOUR },
      }),
    ];

    // WHEN
    const component = await renderTable(rows);

    // THEN
    const badge = component.getByText("mystery", { exact: true });
    await expect.element(badge).toBeVisible();
    expect(badge.element().getAttribute("style")).toBeNull();
  });

  test("shows the short commit and copies the full hash", async () => {
    // GIVEN
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("isSecureContext", true);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    const component = await renderTable([generateBranchTableRow({ branch: featureBranch })]);
    await initPointerTracking(component.locator);

    // WHEN
    const copyButton = component.getByRole("button", { name: `Copy commit ${FULL_COMMIT_HASH}` });
    await copyButton.hover();
    await copyButton.click();

    // THEN
    const shortHash = component.getByText("8f3c2a1", { exact: true });
    await expect.element(shortHash).toHaveAttribute("title", FULL_COMMIT_HASH);
    await expect.element(shortHash).toHaveClass("font-mono");
    expect(writeText).toHaveBeenCalledWith(FULL_COMMIT_HASH);
    await copyButton.unhover();
    await copyButton.hover();
    await expect.element(component.getByRole("tooltip", { name: "Copied!" })).toBeVisible();
  });

  test("leaves the commit cell blank with no copy control when the commit is null", async () => {
    // GIVEN
    const rows = [generateBranchTableRow({ branch: featureBranch, repository: { commit: null } })];

    // WHEN
    const component = await renderTable(rows);

    // THEN
    await expect.element(component.getByText("In Sync", { exact: true })).toBeVisible();
    expect(cellOf(component.container, "Commit")?.textContent).toBe("");
    expect(component.getByRole("button", { name: /Copy commit/ }).query()).toBeNull();
  });

  test("shows no unreachable icon, upstream, behind-by or last-import detail", async () => {
    // GIVEN
    const rows = [
      generateBranchTableRow({
        branch: featureBranch,
        repository: { operationalStatus: OPERATIONAL_STATUS.errorCred },
      }),
    ];

    // WHEN
    const component = await renderTable(rows);

    // THEN
    await expect.element(component.getByText("In Sync", { exact: true })).toBeVisible();
    expect(component.getByRole("img", { name: "Credential Error" }).query()).toBeNull();
    expect(component.container.textContent).not.toMatch(/upstream|behind by|last import/i);
  });

  test("shows one spinner in the Repository cell and blank Git state and Commit while pending", async () => {
    // GIVEN
    const okRow = generateBranchTableRow({ branch: featureBranch });
    const pendingRow: BranchTableRow = {
      id: okRow.branch.id,
      branch: okRow.branch,
      state: "pending",
      repository: null,
    };

    // WHEN
    const component = await renderTable([pendingRow]);

    // THEN
    await expect.element(component.getByRole("status")).toBeVisible();
    expect(component.getByRole("status").elements()).toHaveLength(1);
    const { container } = component;
    expect(cellOf(container, "Repository")?.querySelector("[role='status']")).not.toBeNull();
    expect(cellOf(container, "Git state")?.textContent).toBe("");
    expect(cellOf(container, "Commit")?.textContent).toBe("");
  });
});
