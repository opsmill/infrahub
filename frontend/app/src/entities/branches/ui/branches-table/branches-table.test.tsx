import { focusManager } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { page } from "vitest/browser";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { BranchesTable } from "@/entities/branches/ui/branches-table/branches-table";
import { useGetBranchesPaginated } from "@/entities/branches/ui/queries/get-branches.query";
import { useObjectsCount } from "@/entities/nodes/object/ui/queries/get-objects-count.query";
import { useGetProposedChanges } from "@/entities/proposed-changes/ui/queries/get-proposed-changes.query";
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

const main = generateBranch({
  id: "branch-main",
  name: "main",
  is_default: true,
  sync_with_git: true,
});
const alpha = generateBranch({ id: "branch-alpha", name: "alpha", status: "NEED_REBASE" });
const zulu = generateBranch({ id: "branch-zulu", name: "zulu" });

const oneRepository = generateBranchRepositoriesResult([generateBranchRepository()]);
const threeRepositories = generateBranchRepositoriesResult([
  generateBranchRepository({ id: "repo-1", name: "repo-one" }),
  generateBranchRepository({ id: "repo-2", name: "repo-two" }),
  generateBranchRepository({ id: "repo-3", name: "repo-three" }),
]);

const repositoryConnection = {
  count: 1,
  edges: [
    {
      node: {
        id: "repo-main",
        __typename: "CoreReadOnlyRepository",
        display_label: "main-repo",
        name: { value: "main-repo" },
        commit: { value: null },
        sync_status: { value: "in-sync", label: "In Sync", color: null, description: null },
        operational_status: { value: "online", label: "Online", color: null },
      },
    },
  ],
};

const graphQLResponseFor = (url: string) => {
  if (url.endsWith("/graphql/alpha")) {
    return {
      data: null,
      errors: [{ message: "Repository index unavailable", extensions: { code: "NODE_NOT_FOUND" } }],
    };
  }
  if (url.endsWith("/graphql/zulu")) {
    return {
      data: null,
      errors: [
        {
          message: "You do not have one of the following permissions",
          extensions: { code: "PERMISSION_DENIED", http_status: 403 },
        },
      ],
    };
  }
  return {
    data: {
      CoreGenericRepository: repositoryConnection,
      CoreReadOnlyRepository: repositoryConnection,
    },
  };
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
    vi.unstubAllGlobals();
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

  test("issues one repository request per branch, shared by both of its cells", async () => {
    // GIVEN
    vi.mocked(getBranchRepositories).mockResolvedValue(threeRepositories);

    // WHEN
    const component = await render(<BranchesTable />);

    // THEN
    await expect.element(component.getByRole("link", { name: "+2 more" }).nth(2)).toBeVisible();
    await expect.element(component.getByText("3/3", { exact: true }).nth(2)).toBeVisible();
    expect(vi.mocked(getBranchRepositories).mock.calls.map(([params]) => params)).toEqual(
      expect.arrayContaining([
        { branchName: "main", syncWithGit: true },
        { branchName: "alpha", syncWithGit: false },
        { branchName: "zulu", syncWithGit: false },
      ])
    );
    for (const name of ["main", "alpha", "zulu"]) expect(requestCount(name)).toBe(1);
  });

  test("a window refocus within staleTime issues no extra repository request", async () => {
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

    // THEN
    await expect.poll(() => ["main", "alpha", "zulu"].map(requestCount)).toEqual([1, 1, 1]);
  });

  test("reads Could not load repositories and No permission on one row each, with no toast", async () => {
    // GIVEN
    const { getBranchRepositories: realGetBranchRepositories } = await vi.importActual<
      typeof import("@/entities/repository/domain/use-cases/get-branch-repositories")
    >("@/entities/repository/domain/use-cases/get-branch-repositories");
    vi.mocked(getBranchRepositories).mockImplementation(realGetBranchRepositories);
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => Response.json(graphQLResponseFor(url)))
    );

    // WHEN
    const component = await render(<BranchesTable />);

    // THEN
    await expect.element(component.getByText("Could not load repositories")).toBeVisible();
    await expect.element(component.getByText("No permission")).toBeVisible();
    await expect.element(component.getByRole("link", { name: "main-repo" })).toBeVisible();
    await expect.element(component.getByText("in-sync", { exact: true })).toBeVisible();
    expect(identifierCellNames(component.container)).toEqual(["main", "alpha", "zulu"]);
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(page.getByRole("alert").elements()).toHaveLength(0);
  });
});
