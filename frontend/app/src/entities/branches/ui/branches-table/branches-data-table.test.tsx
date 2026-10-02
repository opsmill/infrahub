import { beforeEach, describe, expect, test, vi } from "vitest";

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
    const branches = [main, feature];
    const component = await render(
      <BranchesDataTable
        columns={getBranchTableColumns()}
        data={toBranchTableRows(
          branches,
          Object.fromEntries(
            branches.map((branch) => [
              branch.name,
              { status: "ok" as const, repositories: [], counts: [] },
            ])
          )
        )}
      />
    );

    // WHEN
    await component.getByRole("checkbox", { name: "Select feature" }).click({ force: true });
    await component.getByRole("button", { name: "Delete" }).click();

    // THEN
    await expect.element(component.getByRole("toolbar")).toHaveTextContent("1 selected");
    await expect.element(component.getByRole("dialog")).toHaveTextContent("`feature`");
  });
});
