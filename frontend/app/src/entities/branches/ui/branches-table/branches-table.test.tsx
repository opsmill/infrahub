import { focusManager } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { BranchesTable } from "@/entities/branches/ui/branches-table/branches-table";
import { useGetBranchesPaginated } from "@/entities/branches/ui/queries/get-branches.query";
import { useObjectsCount } from "@/entities/nodes/object/ui/queries/get-objects-count.query";
import { useGetProposedChanges } from "@/entities/proposed-changes/ui/queries/get-proposed-changes.query";
import type { BranchRepositoriesResult } from "@/entities/repository/domain/model/branch-repository";
import { getBranchRepositories } from "@/entities/repository/domain/use-cases/get-branch-repositories";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

import { render } from "../../../../../tests/components/render";
import { generateBranch } from "../../../../../tests/fake/branch";
import {
  generateBranchRepositoriesResult,
  generateBranchRepository,
} from "../../../../../tests/fake/branch-repositories";

vi.mock("@/entities/authentication/ui/auth-provider");
vi.mock("@/entities/branches/ui/queries/get-branches.query");
vi.mock("@/entities/proposed-changes/ui/queries/get-proposed-changes.query");
vi.mock("@/entities/schema/ui/hooks/useSchema");
vi.mock("@/entities/nodes/object/ui/queries/get-objects-count.query");
vi.mock(
  "@/entities/repository/domain/use-cases/get-branch-repositories",
  async (importOriginal) => ({
    ...(await importOriginal<
      typeof import("@/entities/repository/domain/use-cases/get-branch-repositories")
    >()),
    getBranchRepositories: vi.fn(),
  })
);

const main = generateBranch({ id: "branch-main", name: "main", is_default: true });
const alpha = generateBranch({ id: "branch-alpha", name: "alpha", status: "NEED_REBASE" });
const zulu = generateBranch({ id: "branch-zulu", name: "zulu" });

const oneRepository = generateBranchRepositoriesResult([generateBranchRepository()]);
const threeRepositories = generateBranchRepositoriesResult([
  generateBranchRepository({ id: "repo-1", name: "repo-one" }),
  generateBranchRepository({ id: "repo-2", name: "repo-two" }),
  generateBranchRepository({ id: "repo-3", name: "repo-three" }),
]);

const deferred = () => {
  let resolve: (value: BranchRepositoriesResult) => void = () => {};
  const promise = new Promise<BranchRepositoriesResult>((res) => {
    resolve = res;
  });
  return { promise, resolve };
};

const identifierCellNames = (container: HTMLElement) =>
  [...container.querySelectorAll('[data-testid="branch-identifier-cell"] a')].map((link) =>
    link.textContent?.trim()
  );

const requestCount = (branchName: string) =>
  vi.mocked(getBranchRepositories).mock.calls.filter(([params]) => params.branchName === branchName)
    .length;

describe("BranchesTable", () => {
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
    vi.mocked(useGetBranchesPaginated).mockReturnValue({
      data: { pages: [[zulu, main, alpha]] },
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isPending: false,
      isFetchingNextPage: false,
    } as unknown as ReturnType<typeof useGetBranchesPaginated>);
  });

  afterEach(() => {
    focusManager.setFocused(undefined);
    vi.clearAllMocks();
  });

  test("renders branch name, status and proposed changes while repositories are pending", async () => {
    // GIVEN
    vi.mocked(getBranchRepositories).mockReturnValue(new Promise(() => {}));

    // WHEN
    const component = await render(<BranchesTable />);

    // THEN
    await expect.element(component.getByRole("link", { name: "alpha" })).toBeVisible();
    await expect.element(component.getByText("Rebase needed")).toBeVisible();
    await expect.element(component.getByRole("link", { name: "Add VLANs" }).first()).toBeVisible();
    expect(identifierCellNames(component.container)).toEqual(["main", "alpha", "zulu"]);
    expect(
      component.getByTestId("branches-table").getByRole("status").elements().length
    ).toBeGreaterThanOrEqual(3);
  });

  test("grows a branch from one row to three in place once its repositories load", async () => {
    // GIVEN
    const alphaRequest = deferred();
    vi.mocked(getBranchRepositories).mockImplementation(({ branchName }) =>
      branchName === "alpha" ? alphaRequest.promise : Promise.resolve(oneRepository)
    );
    const component = await render(<BranchesTable />);
    await expect.element(component.getByRole("link", { name: "alpha" })).toBeVisible();
    expect(identifierCellNames(component.container)).toEqual(["main", "alpha", "zulu"]);

    // WHEN
    alphaRequest.resolve(threeRepositories);

    // THEN
    await expect.element(component.getByRole("link", { name: "repo-three" })).toBeVisible();
    expect(identifierCellNames(component.container)).toEqual([
      "main",
      "alpha",
      "alpha",
      "alpha",
      "zulu",
    ]);
  });

  test("a window refocus issues at most one repository request per loaded branch", async () => {
    // GIVEN
    vi.mocked(getBranchRepositories).mockResolvedValue(oneRepository);
    const component = await render(<BranchesTable />);
    await expect
      .element(component.getByRole("link", { name: "infrastructure-templates" }).nth(2))
      .toBeVisible();
    for (const name of ["main", "alpha", "zulu"]) expect(requestCount(name)).toBe(1);

    // WHEN
    focusManager.setFocused(false);
    focusManager.setFocused(true);
    await new Promise((resolve) => setTimeout(resolve, 100));

    // THEN
    for (const name of ["main", "alpha", "zulu"]) expect(requestCount(name)).toBeLessThanOrEqual(2);
  });
});
