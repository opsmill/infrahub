import { afterEach, describe, expect, test, vi } from "vitest";

import { Id } from "@/shared/components/ui/id";

import { getBranchesFromApi } from "@/entities/branches/api/get-branches-from-api";
import { getNodeLabelFromApi } from "@/entities/nodes/object/api/get-display-label-from-api";

import { render } from "../../../../tests/components/render";

vi.mock("@/entities/branches/api/get-branches-from-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/entities/branches/api/get-branches-from-api")>()),
  getBranchesFromApi: vi.fn(),
}));
vi.mock("@/entities/nodes/object/api/get-display-label-from-api");

type BranchesApiResult = Awaited<ReturnType<typeof getBranchesFromApi>>;

describe("Id", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  test("shows that the name is not found, without querying a branch that no longer exists", async () => {
    // GIVEN
    vi.mocked(getBranchesFromApi).mockResolvedValue({
      data: {
        InfrahubBranch: {
          edges: [
            {
              node: {
                id: "branch-main",
                name: { value: "main" },
                description: { value: null },
                origin_branch: { value: null },
                branched_from: { value: "2026-01-01T00:00:00Z" },
                status: { value: "OPEN" },
                created_at: "2026-01-01T00:00:00Z",
                sync_with_git: { value: false },
                is_default: { value: true },
                schema_differs_from_default_branch: { value: false },
              },
              node_metadata: null,
            },
          ],
        },
      },
    } as unknown as BranchesApiResult);

    // WHEN
    const component = await render(
      <Id id="18a2e83c-0e80-fa90-3392-c51809fb54cf" kind="BuiltinTag" branch="merged-and-deleted" />
    );

    // THEN
    await expect.element(component.getByText("Name not found")).toBeVisible();
    expect(getNodeLabelFromApi).not.toHaveBeenCalled();
  });
});
