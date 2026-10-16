import { describe, expect, it, vi } from "vitest";

import { getRepositoryPushStateFromApi } from "@/entities/repository/api/get-repository-push-state-from-api";

import { getRepositoryPushState } from "./get-repository-push-state";

vi.mock("@/entities/repository/api/get-repository-push-state-from-api");

type ApiResult = Awaited<ReturnType<typeof getRepositoryPushStateFromApi>>;
type RepositoryNode = NonNullable<ApiResult["data"]["CoreRepository"]["edges"][number]["node"]>;

const mockRepository = (node: RepositoryNode) => {
  vi.mocked(getRepositoryPushStateFromApi).mockResolvedValue({
    data: { CoreRepository: { edges: [{ node }] } },
  });
};

const repositoryNode = (overrides: Partial<RepositoryNode> = {}): RepositoryNode => ({
  id: "repo-1",
  delivery_status: null,
  delivery_failure_cause: null,
  delivery_error: null,
  delivery_queue: null,
  delivery_last_abandonment: null,
  ...overrides,
});

describe("getRepositoryPushState", () => {
  it("reads a repository that never pushed as nothing pending", async () => {
    // GIVEN
    mockRepository(repositoryNode());

    // WHEN
    const state = await getRepositoryPushState({ repositoryId: "repo-1", branchName: "primary" });

    // THEN
    expect(getRepositoryPushStateFromApi).toHaveBeenCalledWith({
      repositoryId: "repo-1",
      branchName: "primary",
    });
    expect(state).toEqual({
      status: "none",
      statusLabel: "none",
      statusColor: null,
      cause: null,
      causeLabel: null,
      error: null,
      pendingMerges: [],
      queueVersion: 0,
      lastAbandonedPush: null,
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
    const state = await getRepositoryPushState({ repositoryId: "repo-1", branchName: "primary" });

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
      queueVersion: 2,
      lastAbandonedPush: null,
    });
  });

  it("maps the last abandoned push with the abandoned merges and the dropped import", async () => {
    // GIVEN
    const abandonedMerge = {
      entry_id: "entry-1",
      source_branch: "feature-a",
      source_git_branch: "feature-a",
      source_commit: "4b825dc642cb6eb9a060e54bf8d69288fbee4904",
      merged_at: "2026-10-02T09:14:03.120000+00:00",
      delete_source_git_branch: false,
    };
    mockRepository(
      repositoryNode({
        delivery_queue: { value: { format: 1, version: 3, entries: [] } },
        delivery_last_abandonment: {
          value: {
            format: 1,
            abandoned_at: "2026-10-03T08:00:00.000000+00:00",
            account_id: "account-1",
            account_name: "admin",
            queue_version: 2,
            recorded_commit: "9daeafb9864cf43055ae93beb0afd6c7d144bfa4",
            import_owed_commit: "9daeafb9864cf43055ae93beb0afd6c7d144bfa4",
            entries: [abandonedMerge],
          },
        },
      })
    );

    // WHEN
    const state = await getRepositoryPushState({ repositoryId: "repo-1", branchName: "primary" });

    // THEN
    expect(state).toMatchObject({ status: "none", pendingMerges: [], queueVersion: 3 });
    expect(state.lastAbandonedPush).toEqual({
      format: 1,
      abandoned_at: "2026-10-03T08:00:00.000000+00:00",
      account_name: "admin",
      recorded_commit: "9daeafb9864cf43055ae93beb0afd6c7d144bfa4",
      import_owed_commit: "9daeafb9864cf43055ae93beb0afd6c7d144bfa4",
      entries: [
        {
          entry_id: "entry-1",
          source_branch: "feature-a",
          source_commit: abandonedMerge.source_commit,
          merged_at: abandonedMerge.merged_at,
        },
      ],
    });
  });

  it("reads a status or a cause it does not know as an action to take, with the backend's label", async () => {
    // GIVEN
    mockRepository(
      repositoryNode({
        delivery_status: { value: "blocked", label: "Blocked", color: "#f87171" },
        delivery_failure_cause: { value: "quota", label: "Quota exceeded" },
      })
    );

    // WHEN
    const state = await getRepositoryPushState({ repositoryId: "repo-1", branchName: "primary" });

    // THEN
    expect(state).toMatchObject({
      status: "action-required",
      statusLabel: "Blocked",
      cause: "unclassified",
      causeLabel: "Quota exceeded",
    });
  });

  it("fails with a readable message when the pending pushes cannot be read", async () => {
    // GIVEN
    mockRepository(repositoryNode({ delivery_queue: { value: { format: 2, entries: [] } } }));

    // WHEN
    const result = getRepositoryPushState({ repositoryId: "repo-1", branchName: "primary" });

    // THEN
    await expect(result).rejects.toThrow("Cannot read the pending pushes of this repository.");
  });

  it("fails with a readable message when the last abandoned push cannot be read", async () => {
    // GIVEN
    mockRepository(
      repositoryNode({ delivery_last_abandonment: { value: { format: 2, entries: [] } } })
    );

    // WHEN
    const result = getRepositoryPushState({ repositoryId: "repo-1", branchName: "primary" });

    // THEN
    await expect(result).rejects.toThrow("Cannot read the last abandoned push of this repository.");
  });
});
