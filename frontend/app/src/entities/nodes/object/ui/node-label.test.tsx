import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Provider } from "jotai";
import { NuqsAdapter } from "nuqs/adapters/react-router/v7";
import type React from "react";
import { BrowserRouter } from "react-router";
import { afterEach, describe, expect, test, vi } from "vitest";
import { render as renderFromVitest } from "vitest-browser-react";

import { store } from "@/shared/stores";

import { getBranchesFromApi } from "@/entities/branches/api/get-branches-from-api";
import { BranchContext } from "@/entities/branches/ui/branches-provider";
import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import { getNodeLabelFromApi } from "@/entities/nodes/object/api/get-display-label-from-api";
import { NodeLabel } from "@/entities/nodes/object/ui/node-label";

import { render } from "../../../../../tests/components/render";
import { generateBranch } from "../../../../../tests/fake/branch";

vi.mock("@/entities/branches/api/get-branches-from-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/entities/branches/api/get-branches-from-api")>()),
  getBranchesFromApi: vi.fn(),
}));
vi.mock("@/entities/nodes/object/api/get-display-label-from-api");

type BranchesApiResult = Awaited<ReturnType<typeof getBranchesFromApi>>;
type NodeLabelApiResult = Awaited<ReturnType<typeof getNodeLabelFromApi>>;

const NODE_ID = "18a2e83c-0e80-fa90-3392-c51809fb54cf";
const EXISTING_BRANCH = "feature-open";

const branchEdge = (name: string, isDefault: boolean) => ({
  node: {
    id: `branch-${name}`,
    name: { value: name },
    description: { value: null },
    origin_branch: { value: null },
    branched_from: { value: "2026-01-01T00:00:00Z" },
    status: { value: "OPEN" },
    created_at: "2026-01-01T00:00:00Z",
    sync_with_git: { value: false },
    is_default: { value: isDefault },
    schema_differs_from_default_branch: { value: false },
  },
  node_metadata: null,
});

const branchesResult = {
  data: {
    InfrahubBranch: { edges: [branchEdge("main", true), branchEdge(EXISTING_BRANCH, false)] },
  },
} as unknown as BranchesApiResult;

const mockBranches = () => vi.mocked(getBranchesFromApi).mockResolvedValue(branchesResult);

// Renders with a stale branch list already cached, so a label reads it before the list is fetched again.
const renderWithCachedBranches = (ui: React.ReactElement, cachedBranchNames: string[]) => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(
    branchesQueryKeys.all,
    cachedBranchNames.map((name) =>
      generateBranch({ id: `branch-${name}`, name, is_default: name === "main" })
    )
  );
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <NuqsAdapter>
      <Provider store={store}>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <BranchContext value={{ currentBranch: generateBranch(), setCurrentBranch: () => {} }}>
              {children}
            </BranchContext>
          </BrowserRouter>
        </QueryClientProvider>
      </Provider>
    </NuqsAdapter>
  );
  return renderFromVitest(ui, { wrapper });
};

describe("NodeLabel", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  test("shows the node id without querying a branch that no longer exists", async () => {
    // GIVEN
    mockBranches();

    // WHEN
    const component = await render(
      <NodeLabel id={NODE_ID} kind="CoreAccount" branch="merged-and-deleted" />
    );

    // THEN
    await expect.element(component.getByText(NODE_ID)).toBeVisible();
    expect(getBranchesFromApi).toHaveBeenCalled();
    expect(getNodeLabelFromApi).not.toHaveBeenCalled();
  });

  test("queries an existing branch as given, once the branch list is loaded", async () => {
    // GIVEN
    let resolveBranches: (result: BranchesApiResult) => void = () => {};
    vi.mocked(getBranchesFromApi).mockReturnValue(
      new Promise<BranchesApiResult>((resolve) => {
        resolveBranches = resolve;
      })
    );
    vi.mocked(getNodeLabelFromApi).mockResolvedValue({
      data: { CoreAccount: { edges: [] } },
    } as unknown as NodeLabelApiResult);

    // WHEN
    await render(<NodeLabel id={NODE_ID} kind="CoreAccount" branch={EXISTING_BRANCH} />);

    // THEN
    await vi.waitFor(() => expect(getBranchesFromApi).toHaveBeenCalled());
    expect(getNodeLabelFromApi).not.toHaveBeenCalled();

    resolveBranches(branchesResult);

    await vi.waitFor(() =>
      expect(getNodeLabelFromApi).toHaveBeenCalledWith(
        expect.objectContaining({ objectId: NODE_ID, branchName: EXISTING_BRANCH })
      )
    );
    expect(getNodeLabelFromApi).toHaveBeenCalledTimes(1);
  });

  test("requests the label once its branch is in the branch list", async () => {
    // GIVEN
    const createdElsewhere = "created-elsewhere";
    vi.mocked(getBranchesFromApi).mockResolvedValue({
      data: {
        InfrahubBranch: { edges: [branchEdge("main", true), branchEdge(createdElsewhere, false)] },
      },
    } as unknown as BranchesApiResult);
    vi.mocked(getNodeLabelFromApi).mockResolvedValue({
      data: { CoreAccount: { edges: [] } },
    } as unknown as NodeLabelApiResult);

    // WHEN
    await renderWithCachedBranches(
      <NodeLabel id={NODE_ID} kind="CoreAccount" branch={createdElsewhere} />,
      ["main"]
    );

    // THEN
    await vi.waitFor(() =>
      expect(getNodeLabelFromApi).toHaveBeenCalledWith(
        expect.objectContaining({ objectId: NODE_ID, branchName: createdElsewhere })
      )
    );
    expect(getNodeLabelFromApi).toHaveBeenCalledTimes(1);
  });

  test("queries the given branch when the branch list cannot be loaded", async () => {
    // GIVEN
    vi.mocked(getBranchesFromApi).mockRejectedValue(new Error("branch list unavailable"));
    vi.mocked(getNodeLabelFromApi).mockResolvedValue({
      data: { CoreAccount: { edges: [] } },
    } as unknown as NodeLabelApiResult);

    // WHEN
    await render(<NodeLabel id={NODE_ID} kind="CoreAccount" branch="unlisted-branch" />);

    // THEN
    await vi.waitFor(() =>
      expect(getNodeLabelFromApi).toHaveBeenCalledWith(
        expect.objectContaining({ objectId: NODE_ID, branchName: "unlisted-branch" })
      )
    );
  });
});
