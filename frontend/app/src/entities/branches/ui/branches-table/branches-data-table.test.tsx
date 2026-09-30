import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { type Locator, userEvent } from "vitest/browser";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import type { BranchTableRow } from "@/entities/branches/domain/model/branch-table-row";
import {
  BranchesDataTable,
  COMMIT_TRACK,
  GIT_STATE_TRACK,
  REPOSITORY_TRACK,
} from "@/entities/branches/ui/branches-table/branches-data-table";
import { getBranchTableColumns } from "@/entities/branches/ui/branches-table/get-branch-table-columns";
import { useDeleteBranchesMutation } from "@/entities/branches/ui/queries/delete-branches.mutation";
import { useObjectsCount } from "@/entities/nodes/object/ui/queries/get-objects-count.query";
import { useGetProposedChanges } from "@/entities/proposed-changes/ui/queries/get-proposed-changes.query";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

import { render } from "../../../../../tests/components/render";
import { generateBranch } from "../../../../../tests/fake/branch";
import { generateBranchRepository } from "../../../../../tests/fake/branch-repositories";

vi.mock("@/entities/authentication/ui/auth-provider");
vi.mock("@/entities/proposed-changes/ui/queries/get-proposed-changes.query");
vi.mock("@/entities/schema/ui/hooks/useSchema");
vi.mock("@/entities/nodes/object/ui/queries/get-objects-count.query");
vi.mock("@/entities/branches/ui/queries/delete-branches.mutation");

const COLUMN_COUNT = 11;

const deleteBranches = vi.fn();

const solo = generateBranch({ id: "branch-solo", name: "solo" });
const alpha = generateBranch({ id: "branch-alpha", name: "alpha" });
const zulu = generateBranch({ id: "branch-zulu", name: "zulu" });

const okRows = (branch: BranchListItem, repositoryNames: string[]): BranchTableRow[] =>
  repositoryNames.map((name, index) => ({
    id: index === 0 ? branch.id : `${branch.id}:repo-${name}`,
    branch,
    state: "ok",
    repository: generateBranchRepository({ id: `repo-${name}`, name }),
  }));

const pendingRow = (branch: BranchListItem): BranchTableRow => ({
  id: branch.id,
  branch,
  state: "pending",
  repository: null,
});

const table = (rows: BranchTableRow[]) => (
  <BranchesDataTable columns={getBranchTableColumns()} data={rows} data-testid="branches-table" />
);

const gridOf = (container: HTMLElement) =>
  container.querySelector<HTMLElement>('[data-testid="branches-table"]');

const cellText = (container: HTMLElement, columnIndex: number, rowIndex: number) =>
  gridOf(container)?.children[COLUMN_COUNT * (rowIndex + 1) + columnIndex]?.textContent?.trim();

const splitTracks = (template: string) => {
  const tracks: string[] = [];
  let depth = 0;
  let current = "";
  for (const char of template) {
    if (char === "(") depth++;
    if (char === ")") depth--;
    if (char === " " && depth === 0) {
      if (current) tracks.push(current);
      current = "";
      continue;
    }
    current += char;
  }
  if (current) tracks.push(current);
  return tracks.flatMap((track) => {
    const repeat = /^repeat\((\d+), (.+)\)$/.exec(track);
    return repeat ? Array<string>(Number(repeat[1])).fill(repeat[2] ?? "") : [track];
  });
};

// The checkbox input is visually hidden; its label is the pressable target.
const tick = (checkbox: Locator, options?: { modifiers: ["Shift"] }) =>
  userEvent.click(checkbox.element().closest("label") ?? checkbox.element(), options);

const mockAuth = (isAuthenticated: boolean) =>
  vi.mocked(useAuth).mockReturnValue({
    accessToken: isAuthenticated ? "token" : null,
    isAuthenticated,
    setToken: vi.fn(),
    user: null,
  } as unknown as ReturnType<typeof useAuth>);

describe("BranchesDataTable selection", () => {
  beforeEach(() => {
    mockAuth(true);
    vi.mocked(useSchema).mockReturnValue({ schema: null } as unknown as ReturnType<
      typeof useSchema
    >);
    vi.mocked(useObjectsCount).mockReturnValue({
      data: 0,
      isLoading: false,
    } as unknown as ReturnType<typeof useObjectsCount>);
    vi.mocked(useGetProposedChanges).mockReturnValue({
      data: {
        pages: [{ count: 1, items: [{ id: "pc-1", node: { name: { value: "Add VLANs" } } }] }],
      },
      isPending: false,
    } as unknown as ReturnType<typeof useGetProposedChanges>);
    vi.mocked(useDeleteBranchesMutation).mockReturnValue({
      mutateAsync: deleteBranches,
      isPending: false,
    } as unknown as ReturnType<typeof useDeleteBranchesMutation>);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("renders one row per repository, repeating the branch's name, status and proposed changes", async () => {
    // GIVEN
    const rows = okRows(alpha, ["repo-one", "repo-two", "repo-three"]);

    // WHEN
    const component = await render(table(rows));

    // THEN
    await expect.element(component.getByRole("link", { name: "repo-three" })).toBeVisible();
    const { container } = component;
    for (const [columnIndex, expected] of [
      [0, "alphatest-branch's description"],
      [1, "Open"],
      [2, "Add VLANs"],
    ] as const) {
      expect([0, 1, 2].map((rowIndex) => cellText(container, columnIndex, rowIndex))).toEqual([
        expected,
        expected,
        expected,
      ]);
    }
    expect([0, 1, 2].map((rowIndex) => cellText(container, 3, rowIndex))).toEqual([
      "repo-one",
      "repo-two",
      "repo-three",
    ]);
  });

  test("ticking a non-first row selects the whole branch once", async () => {
    // GIVEN
    const component = await render(table(okRows(alpha, ["repo-one", "repo-two", "repo-three"])));

    // WHEN
    await tick(component.getByRole("checkbox", { name: "Select alpha (repo-two)" }));

    // THEN
    await expect
      .element(component.getByRole("checkbox", { name: "Select alpha", exact: true }))
      .toBeChecked();
    await expect
      .element(component.getByRole("checkbox", { name: "Select alpha (repo-two)" }))
      .toBeChecked();
    await expect
      .element(component.getByRole("checkbox", { name: "Select alpha (repo-three)" }))
      .toBeChecked();
    await expect.element(component.getByTestId("branches-toolbar")).toHaveTextContent("1 selected");
  });

  test("the bulk delete dialog lists a multi-repository branch once", async () => {
    // GIVEN
    const component = await render(table(okRows(alpha, ["repo-one", "repo-two", "repo-three"])));
    await tick(component.getByRole("checkbox", { name: "Select alpha (repo-three)" }));

    // WHEN
    await component.getByRole("button", { name: "Delete" }).click();

    // THEN
    const dialog = component.getByRole("dialog");
    await expect.element(dialog).toHaveTextContent("Are you sure you want to remove the branch");
    expect(dialog.element().textContent?.match(/alpha/g)).toHaveLength(1);
  });

  test("confirming the bulk delete of a multi-repository branch deletes it once", async () => {
    // GIVEN
    const component = await render(table(okRows(alpha, ["repo-one", "repo-two", "repo-three"])));
    await tick(component.getByRole("checkbox", { name: "Select alpha (repo-three)" }));
    await component.getByRole("button", { name: "Delete" }).click();

    // WHEN
    await component.getByRole("dialog").getByRole("button", { name: "Delete" }).click();

    // THEN
    await vi.waitFor(() => expect(deleteBranches).toHaveBeenCalledTimes(1));
    expect(deleteBranches).toHaveBeenCalledWith({ names: ["alpha"], deleteFromGit: false });
  });

  test("shift-click onto a later multi-repository branch's row counts branches", async () => {
    // GIVEN
    const rows = [
      ...okRows(solo, ["repo-one"]),
      ...okRows(alpha, ["repo-one", "repo-two", "repo-three"]),
      ...okRows(zulu, ["repo-one"]),
    ];
    const component = await render(table(rows));
    await tick(component.getByRole("checkbox", { name: "Select solo", exact: true }));

    // WHEN
    await tick(component.getByRole("checkbox", { name: "Select alpha (repo-three)" }), {
      modifiers: ["Shift"],
    });

    // THEN
    await expect.element(component.getByTestId("branches-toolbar")).toHaveTextContent("2 selected");
    await expect
      .element(component.getByRole("checkbox", { name: "Select zulu", exact: true }))
      .not.toBeChecked();
  });

  test("select all counts branches, not rows", async () => {
    // GIVEN
    const rows = [...okRows(alpha, ["repo-one", "repo-two", "repo-three"]), ...okRows(zulu, ["x"])];
    const component = await render(table(rows));

    // WHEN
    await tick(component.getByRole("checkbox", { name: "Select all branches" }));

    // THEN
    await expect.element(component.getByTestId("branches-toolbar")).toHaveTextContent("2 selected");
  });

  test("the header checkbox reflects branches while repository rows are present", async () => {
    // GIVEN
    const rows = [...okRows(alpha, ["repo-one", "repo-two", "repo-three"]), ...okRows(zulu, ["x"])];
    const component = await render(table(rows));
    const header = component.getByRole("checkbox", { name: "Select all branches" });

    // WHEN
    await tick(component.getByRole("checkbox", { name: "Select alpha (repo-two)" }));

    // THEN
    await expect.element(header).toBePartiallyChecked();
    await tick(component.getByRole("checkbox", { name: "Select zulu", exact: true }));
    await expect.element(header).toBeChecked();
    await expect.element(header).not.toBePartiallyChecked();
  });

  test("a logout clears the selection", async () => {
    // GIVEN
    const rows = okRows(alpha, ["repo-one", "repo-two"]);
    const component = await render(table(rows));
    await tick(component.getByRole("checkbox", { name: "Select alpha (repo-two)" }));
    await expect.element(component.getByTestId("branches-toolbar")).toBeVisible();

    // WHEN
    mockAuth(false);
    await component.rerender(table(rows));
    mockAuth(true);
    await component.rerender(table(rows));

    // THEN
    await expect
      .element(component.getByRole("checkbox", { name: "Select alpha", exact: true }))
      .not.toBeChecked();
    expect(component.getByTestId("branches-toolbar").query()).toBeNull();
  });

  test("a selected branch stays selected when it grows from pending to several rows", async () => {
    // GIVEN
    const component = await render(table([pendingRow(alpha), ...okRows(zulu, ["x"])]));
    await tick(component.getByRole("checkbox", { name: "Select alpha", exact: true }));

    // WHEN
    await component.rerender(
      table([...okRows(alpha, ["repo-one", "repo-two", "repo-three"]), ...okRows(zulu, ["x"])])
    );

    // THEN
    await expect
      .element(component.getByRole("checkbox", { name: "Select alpha (repo-three)" }))
      .toBeChecked();
    await expect
      .element(component.getByRole("checkbox", { name: "Select alpha", exact: true }))
      .toBeChecked();
    await expect.element(component.getByTestId("branches-toolbar")).toHaveTextContent("1 selected");
  });

  test("shift-range stays on the intended branches after a branch above expands", async () => {
    // GIVEN
    const mid = generateBranch({ id: "branch-mid", name: "mid" });
    const late = generateBranch({ id: "branch-late", name: "late" });
    const tail = [...okRows(mid, ["x"]), ...okRows(late, ["x"]), ...okRows(zulu, ["x"])];
    const component = await render(table([pendingRow(alpha), ...tail]));
    await tick(component.getByRole("checkbox", { name: "Select mid", exact: true }));
    await component.rerender(
      table([...okRows(alpha, ["repo-one", "repo-two", "repo-three"]), ...tail])
    );

    // WHEN
    await tick(component.getByRole("checkbox", { name: "Select late", exact: true }), {
      modifiers: ["Shift"],
    });

    // THEN
    await expect.element(component.getByTestId("branches-toolbar")).toHaveTextContent("2 selected");
    await expect
      .element(component.getByRole("checkbox", { name: "Select mid", exact: true }))
      .toBeChecked();
    await expect
      .element(component.getByRole("checkbox", { name: "Select late", exact: true }))
      .toBeChecked();
    for (const name of ["Select alpha", "Select alpha (repo-two)", "Select alpha (repo-three)"]) {
      await expect
        .element(component.getByRole("checkbox", { name, exact: true }))
        .not.toBeChecked();
    }
    await expect
      .element(component.getByRole("checkbox", { name: "Select zulu", exact: true }))
      .not.toBeChecked();
  });

  test("only each branch's first-row checkbox is in the tab order", async () => {
    // GIVEN
    const rows = [...okRows(alpha, ["repo-one", "repo-two", "repo-three"]), ...okRows(zulu, ["x"])];

    // WHEN
    const component = await render(table(rows));

    // THEN
    for (const name of ["Select alpha", "Select zulu"]) {
      const checkbox = component.getByRole("checkbox", { name, exact: true });
      await expect.element(checkbox).toBeVisible();
      expect(checkbox.element().tabIndex).toBe(0);
    }
    for (const name of ["Select alpha (repo-two)", "Select alpha (repo-three)"]) {
      expect(component.getByRole("checkbox", { name }).element().tabIndex).toBe(-1);
    }
  });

  test("the grid template has one track per column, with the repository tracks 4th to 6th", async () => {
    // GIVEN
    const rows = okRows(alpha, ["repo-one"]);

    // WHEN
    const component = await render(table(rows));

    // THEN
    await expect.element(component.getByRole("link", { name: "repo-one" })).toBeVisible();
    const tracks = splitTracks(gridOf(component.container)?.style.gridTemplateColumns ?? "");
    expect(tracks).toHaveLength(COLUMN_COUNT);
    expect(tracks.slice(3, 6)).toEqual([REPOSITORY_TRACK, GIT_STATE_TRACK, COMMIT_TRACK]);
  });
});
