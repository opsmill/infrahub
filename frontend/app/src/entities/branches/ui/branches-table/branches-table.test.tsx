import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { page } from "vitest/browser";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { getBranchGitRepositories } from "@/entities/branch-git-status/domain/use-cases/get-branch-git-repositories";
import { getRepositoryBranchStatus } from "@/entities/branch-git-status/domain/use-cases/get-repository-branch-status";
import { BranchesTable } from "@/entities/branches/ui/branches-table/branches-table";
import { useGetBranchesPaginated } from "@/entities/branches/ui/queries/get-branches.query";
import { useObjectsCount } from "@/entities/nodes/object/ui/queries/get-objects-count.query";
import { useGetProposedChanges } from "@/entities/proposed-changes/ui/queries/get-proposed-changes.query";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

import { render } from "../../../../../tests/components/render";
import { generateBranch } from "../../../../../tests/fake/branch";
import {
  generateBranchGitRepository,
  generateRepositoryBranchGitStatusPage,
  generateRepositoryBranchGitStatusWire,
} from "../../../../../tests/fake/branch-git-status";

vi.mock("@/entities/authentication/ui/auth-provider");
vi.mock("@/entities/branches/ui/queries/get-branches.query");
vi.mock("@/entities/proposed-changes/ui/queries/get-proposed-changes.query");
vi.mock("@/entities/schema/ui/hooks/useSchema");
vi.mock("@/entities/nodes/object/ui/queries/get-objects-count.query");
vi.mock("@/entities/branch-git-status/domain/use-cases/get-branch-git-repositories");
vi.mock("@/entities/branch-git-status/domain/use-cases/get-repository-branch-status");

const main = generateBranch({
  id: "branch-main",
  name: "main",
  is_default: true,
  sync_with_git: true,
});
const alpha = generateBranch({ id: "branch-alpha", name: "alpha", status: "NEED_REBASE" });
const zulu = generateBranch({ id: "branch-zulu", name: "zulu" });
const yankee = generateBranch({ id: "branch-yankee", name: "yankee" });

const REPOSITORIES = {
  repositories: [
    generateBranchGitRepository({ id: "repo-1", name: "repo-one" }),
    generateBranchGitRepository({ id: "repo-2", name: "repo-two" }),
    generateBranchGitRepository({ id: "repo-3", name: "repo-three" }),
  ],
  count: 3,
};

const statusErrorResponse = (code: string, message: string) => ({
  data: null,
  errors: [
    { message, extensions: { code, http_status: code === "PERMISSION_DENIED" ? 403 : 404 } },
  ],
});

const serveRealStatusOverFetch = async (respond: (repositoryId: string) => unknown) => {
  const { getRepositoryBranchStatus: real } = await vi.importActual<
    typeof import("@/entities/branch-git-status/domain/use-cases/get-repository-branch-status")
  >("@/entities/branch-git-status/domain/use-cases/get-repository-branch-status");
  vi.mocked(getRepositoryBranchStatus).mockImplementation(real);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: string, init?: RequestInit) => {
      const { variables } = JSON.parse(String(init?.body ?? "{}"));
      return Response.json(respond(variables?.id));
    })
  );
};

const mockBranchPages = (...pages: Array<Array<ReturnType<typeof generateBranch>>>) => {
  vi.mocked(useGetBranchesPaginated).mockReturnValue({
    data: { pages },
    fetchNextPage: vi.fn(),
    hasNextPage: false,
    isPending: false,
    isFetchingNextPage: false,
  } as unknown as ReturnType<typeof useGetBranchesPaginated>);
};

const identifierCellNames = (container: HTMLElement) =>
  [...container.querySelectorAll('[data-testid="branch-identifier-cell"] a')].map((link) =>
    link.textContent?.trim()
  );

const expectNoToast = async () => {
  for (let sample = 0; sample < 5; sample += 1) {
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(page.getByRole("alert").elements()).toHaveLength(0);
  }
};

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
    mockBranchPages([zulu, main, alpha]);
    vi.mocked(getBranchGitRepositories).mockResolvedValue(REPOSITORIES);
    vi.mocked(getRepositoryBranchStatus).mockResolvedValue(
      generateRepositoryBranchGitStatusPage({ branchNames: ["main", "alpha", "zulu"] })
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  test("renders branch name, status and proposed changes while repositories are pending", async () => {
    // GIVEN
    vi.mocked(getBranchGitRepositories).mockReturnValue(new Promise(() => {}));

    // WHEN
    const component = await render(<BranchesTable />);

    // THEN
    await expect.element(component.getByRole("link", { name: "alpha" })).toBeVisible();
    await expect.element(component.getByText("Rebase needed")).toBeVisible();
    await expect.element(component.getByRole("link", { name: "Add VLANs" }).first()).toBeVisible();
    expect(identifierCellNames(component.container)).toEqual(["main", "alpha", "zulu"]);
    expect(component.getByText("Loading repositories").elements()).toHaveLength(3);
  });

  test("issues one repository-list request and one status request per repository", async () => {
    // WHEN
    const component = await render(<BranchesTable />);

    // THEN
    await expect
      .element(component.getByTestId("branch-git-state-cell-zulu"))
      .toHaveTextContent("3/3");
    await expect
      .element(component.getByRole("link", { name: "+2 more repositories on zulu" }))
      .toBeVisible();
    expect(vi.mocked(getBranchGitRepositories).mock.calls).toEqual([[{ limit: 500, offset: 0 }]]);
    expect(
      vi.mocked(getRepositoryBranchStatus).mock.calls.map(([params]) => params.repositoryId)
    ).toEqual(["repo-1", "repo-2", "repo-3"]);
  });

  test("loading a second page of branches issues no new status request", async () => {
    // GIVEN
    vi.mocked(getRepositoryBranchStatus).mockResolvedValue(
      generateRepositoryBranchGitStatusPage({ branchNames: ["main", "alpha", "zulu", "yankee"] })
    );
    const component = await render(<BranchesTable />);
    await expect
      .element(component.getByTestId("branch-git-state-cell-zulu"))
      .toHaveTextContent("3/3");

    // WHEN
    mockBranchPages([zulu, main, alpha], [yankee]);
    await component.rerender(<BranchesTable />);

    // THEN
    await expect
      .element(component.getByTestId("branch-git-state-cell-yankee"))
      .toHaveTextContent("3/3");
    expect(getBranchGitRepositories).toHaveBeenCalledTimes(1);
    expect(getRepositoryBranchStatus).toHaveBeenCalledTimes(3);
  });

  test("reads No permission on every row when every status read is denied, with no toast", async () => {
    // GIVEN
    await serveRealStatusOverFetch(() =>
      statusErrorResponse("PERMISSION_DENIED", "You do not have one of the following permissions")
    );

    // WHEN
    const component = await render(<BranchesTable />);

    // THEN
    await expect.element(component.getByText("No permission").nth(2)).toBeVisible();
    expect(component.getByText("No permission").elements()).toHaveLength(3);
    expect(identifierCellNames(component.container)).toEqual(["main", "alpha", "zulu"]);
    await expectNoToast();
  });

  test("keeps the loaded repositories and notes the one whose status read failed, with no toast", async () => {
    // GIVEN
    await serveRealStatusOverFetch((repositoryId) =>
      repositoryId === "repo-2"
        ? statusErrorResponse("NODE_NOT_FOUND", "Repository index unavailable")
        : {
            data: {
              InfrahubRepositoryBranchStatus: {
                count: 1,
                edges: [{ node: generateRepositoryBranchGitStatusWire({ branchName: "main" }) }],
              },
            },
          }
    );

    // WHEN
    const component = await render(<BranchesTable />);

    // THEN
    await expect
      .element(component.getByTestId("branch-repositories-cell-main"))
      .toHaveTextContent(/repo-one.*\+1 more.*1 repository could not be loaded/);
    await expect
      .element(component.getByTestId("branch-repositories-cell-alpha"))
      .toHaveTextContent("1 repository could not be loadedrepo-two: Repository index unavailable");
    expect(component.getByText("Could not load repositories").query()).toBeNull();
    await expectNoToast();
  });
});
