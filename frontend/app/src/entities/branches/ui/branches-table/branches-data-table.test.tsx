import { beforeEach, describe, expect, test, vi } from "vitest";

import { COLUMN_MAX_WIDTH, WIDE_COLUMN_MAX_WIDTH } from "@/shared/components/table/style";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { toBranchTableRows } from "@/entities/branches/ui/branches-table/branch-table-row";
import { BranchesDataTable } from "@/entities/branches/ui/branches-table/branches-data-table";
import { getBranchTableColumns } from "@/entities/branches/ui/branches-table/get-branch-table-columns";
import { useObjectsCount } from "@/entities/nodes/object/ui/queries/get-objects-count.query";
import { useGetProposedChanges } from "@/entities/proposed-changes/ui/queries/get-proposed-changes.query";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

import { render } from "../../../../../tests/components/render";
import { generateBranch } from "../../../../../tests/fake/branch";

vi.mock("@/entities/authentication/ui/auth-provider");
vi.mock("@/entities/proposed-changes/ui/queries/get-proposed-changes.query");
vi.mock("@/entities/schema/ui/hooks/useSchema");
vi.mock("@/entities/nodes/object/ui/queries/get-objects-count.query");

const main = generateBranch({ id: "branch-main", name: "main", is_default: true });
const feature = generateBranch({ id: "branch-feature", name: "feature", sync_with_git: false });

const FIT = `fit-content(${COLUMN_MAX_WIDTH})`;

describe("BranchesDataTable", () => {
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

  test("ticking a row selects it and offers to delete that branch", async () => {
    // GIVEN
    const component = await render(
      <BranchesDataTable
        columns={getBranchTableColumns()}
        data={toBranchTableRows([main, feature], {})}
      />
    );

    // WHEN
    await component.getByRole("checkbox", { name: "Select feature" }).click({ force: true });
    await component.getByRole("button", { name: "Delete" }).click();

    // THEN
    await expect.element(component.getByRole("toolbar")).toHaveTextContent("1 selected");
    await expect.element(component.getByRole("dialog")).toHaveTextContent("`feature`");
  });

  test("sizes each column by its own track, whatever its position", async () => {
    // GIVEN
    const columns = getBranchTableColumns();

    // WHEN
    const inOrder = await render(
      <BranchesDataTable columns={columns} data={[]} data-testid="in-order" />
    );
    const reversed = await render(
      <BranchesDataTable columns={[...columns].reverse()} data={[]} data-testid="reversed" />
    );

    // THEN
    const tracks = [
      `fit-content(${WIDE_COLUMN_MAX_WIDTH})`,
      FIT,
      "minmax(150px, 200px)",
      "minmax(12rem, 18rem)",
      "9rem",
      FIT,
      FIT,
      FIT,
      FIT,
      "2.5rem",
    ];
    const templateOf = (element: Element) =>
      element instanceof HTMLElement ? element.style.gridTemplateColumns : null;
    expect(templateOf(inOrder.getByTestId("in-order").element())).toBe(tracks.join(" "));
    expect(templateOf(reversed.getByTestId("reversed").element())).toBe(
      [...tracks].reverse().join(" ")
    );
  });
});
