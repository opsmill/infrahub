import { describe, expect, it, vi } from "vitest";

import { getDeliveryStateFromApi } from "@/entities/repository/api/get-delivery-state-from-api";

import { getDeliveryState } from "./get-delivery-state";

vi.mock("@/entities/repository/api/get-delivery-state-from-api");

type ApiResult = Awaited<ReturnType<typeof getDeliveryStateFromApi>>;
type RepositoryNode = NonNullable<ApiResult["data"]["CoreRepository"]["edges"][number]["node"]>;

const mockRepository = (node: RepositoryNode) => {
  vi.mocked(getDeliveryStateFromApi).mockResolvedValue({
    data: { CoreRepository: { edges: [{ node }] } },
  });
};

const repositoryNode = (overrides: Partial<RepositoryNode> = {}): RepositoryNode => ({
  id: "repo-1",
  delivery_status: null,
  delivery_failure_cause: null,
  delivery_error: null,
  delivery_queue: null,
  ...overrides,
});

describe("getDeliveryState", () => {
  it("reads a repository that never pushed as nothing pending", async () => {
    // GIVEN
    mockRepository(repositoryNode());

    // WHEN
    const state = await getDeliveryState({ repositoryId: "repo-1", branchName: "primary" });

    // THEN
    expect(state).toEqual({
      status: "none",
      statusLabel: null,
      statusColor: null,
      cause: null,
      causeLabel: null,
      error: null,
      pendingMerges: [],
    });
  });

  it("maps a refused push with its cause, the remote's message and the pending merges in order", async () => {
    // GIVEN
    const firstMerge = {
      entry_id: "entry-1",
      source_branch: "feature-a",
      source_git_branch: "feature-a",
      source_commit: "4b825dc642cb6eb9a060e54bf8d69288fbee4904",
      merged_at: "2026-10-02T09:14:03.120000+00:00",
      delete_source_git_branch: false,
    };
    const secondMerge = { ...firstMerge, entry_id: "entry-2", source_branch: "feature-b" };
    mockRepository(
      repositoryNode({
        delivery_status: {
          value: "action-required",
          label: "Action required",
          color: "#f87171",
        },
        delivery_failure_cause: {
          value: "permission",
          label: "Push refused by the remote",
        },
        delivery_error: {
          value: "remote: error: GH006: Protected branch update failed",
        },
        delivery_queue: {
          value: { format: 1, version: 2, entries: [firstMerge, secondMerge] },
        },
      })
    );

    // WHEN
    const state = await getDeliveryState({ repositoryId: "repo-1", branchName: "primary" });

    // THEN
    expect(state).toEqual({
      status: "action-required",
      statusLabel: "Action required",
      statusColor: "#f87171",
      cause: "permission",
      causeLabel: "Push refused by the remote",
      error: "remote: error: GH006: Protected branch update failed",
      pendingMerges: [
        {
          entry_id: "entry-1",
          source_branch: "feature-a",
          source_commit: firstMerge.source_commit,
          merged_at: firstMerge.merged_at,
        },
        {
          entry_id: "entry-2",
          source_branch: "feature-b",
          source_commit: firstMerge.source_commit,
          merged_at: firstMerge.merged_at,
        },
      ],
    });
  });
});
