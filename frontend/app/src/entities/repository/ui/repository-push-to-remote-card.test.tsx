import { beforeEach, describe, expect, test, vi } from "vitest";

import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";
import type { RepositoryPushState } from "@/entities/repository/domain/model/repository-push-state";
import { getRepositoryPushState } from "@/entities/repository/domain/use-cases/get-repository-push-state";

import { render } from "../../../../tests/components/render";
import { generateBranch } from "../../../../tests/fake/branch";
import { RepositoryPushToRemoteCard } from "./repository-push-to-remote-card";

vi.mock("@/entities/branches/ui/queries/get-branches.query");
vi.mock("@/entities/repository/domain/use-cases/get-repository-push-state");

const IMPORTS_PAUSED =
  "Imports from the remote default branch are paused until the pending pushes clear.";

const FIRST_COMMIT = "4b825dc642cb6eb9a060e54bf8d69288fbee4904";

const refusedPush: RepositoryPushState = {
  status: "action-required",
  statusLabel: "Action required",
  statusColor: "#f87171",
  cause: "permission",
  causeLabel: "Push refused by the remote",
  error:
    "remote: error: GH006: Protected branch update failed for refs/heads/main.\n ! [remote rejected] HEAD -> main",
  pendingMerges: [
    {
      entry_id: "entry-1",
      source_branch: "feature-a",
      source_commit: FIRST_COMMIT,
      merged_at: "2026-10-02T09:14:03.120000+00:00",
    },
    {
      entry_id: "entry-2",
      source_branch: "feature-b",
      source_commit: "9daeafb9864cf43055ae93beb0afd6c7d144bfa4",
      merged_at: "2026-10-02T10:20:00.000000+00:00",
    },
  ],
  queueVersion: 2,
  lastAbandonment: null,
};

describe("RepositoryPushToRemoteCard", () => {
  beforeEach(() => {
    vi.resetAllMocks();

    // The selected branch, "test-branch", is not the default branch.
    vi.mocked(useGetBranches).mockReturnValue({
      data: [
        generateBranch({ name: "test-branch" }),
        generateBranch({ name: "primary", is_default: true }),
      ],
    } as unknown as ReturnType<typeof useGetBranches>);
  });

  test("reads the push state from the default branch while another branch is selected", async () => {
    // GIVEN
    vi.mocked(getRepositoryPushState).mockResolvedValue(refusedPush);

    // WHEN
    const component = await render(<RepositoryPushToRemoteCard repositoryId="repo-1" />);

    // THEN
    await expect.element(component.getByText("Action required")).toBeVisible();
    expect(getRepositoryPushState).toHaveBeenCalledWith({
      repositoryId: "repo-1",
      branchName: "primary",
    });
  });

  test("shows the cause, the required action, the paused imports, the remote's message and the pending merges", async () => {
    // GIVEN
    vi.mocked(getRepositoryPushState).mockResolvedValue(refusedPush);

    // WHEN
    const component = await render(<RepositoryPushToRemoteCard repositoryId="repo-1" />);

    // THEN
    await expect.element(component.getByText("Push to remote")).toBeVisible();
    await expect.element(component.getByText("Push refused by the remote")).toBeVisible();
    await expect
      .element(
        component.getByText("Grant push permission or lift the branch protection, then retry.")
      )
      .toBeVisible();
    await expect.element(component.getByText(IMPORTS_PAUSED)).toBeVisible();
    const message = component.getByText(/^remote: error: GH006/);
    await expect.element(message).toBeVisible();
    expect(message.element().textContent).toBe(refusedPush.error);
    const firstMerge = component.getByText("feature-a", { exact: true });
    const secondMerge = component.getByText("feature-b", { exact: true });
    await expect.element(firstMerge).toBeVisible();
    await expect.element(secondMerge).toBeVisible();
    await expect.element(component.getByText("4b825dc", { exact: true })).toBeVisible();
    expect(firstMerge.element().compareDocumentPosition(secondMerge.element())).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING
    );
    await expect.element(component.baseElement).not.toHaveTextContent(FIRST_COMMIT);
  });

  test("shows the paused imports and no cause while the first attempt runs", async () => {
    // GIVEN
    vi.mocked(getRepositoryPushState).mockResolvedValue({
      ...refusedPush,
      status: "pending",
      statusLabel: "Pending",
      statusColor: "#60a5fa",
      cause: null,
      causeLabel: null,
      error: null,
    });

    // WHEN
    const component = await render(<RepositoryPushToRemoteCard repositoryId="repo-1" />);

    // THEN
    await expect.element(component.getByText("Pending", { exact: true })).toBeVisible();
    await expect.element(component.getByText(IMPORTS_PAUSED)).toBeVisible();
    await expect.element(component.getByText("Cause", { exact: true })).not.toBeInTheDocument();
  });

  test("shows no cause, required action or message from the last failure while a retry runs", async () => {
    // GIVEN
    vi.mocked(getRepositoryPushState).mockResolvedValue({
      ...refusedPush,
      status: "pending",
      statusLabel: "Pending",
      statusColor: "#60a5fa",
    });

    // WHEN
    const component = await render(<RepositoryPushToRemoteCard repositoryId="repo-1" />);

    // THEN
    await expect.element(component.getByText("Pending", { exact: true })).toBeVisible();
    await expect.element(component.getByText(IMPORTS_PAUSED)).toBeVisible();
    await expect.element(component.getByText("feature-a", { exact: true })).toBeVisible();
    await expect.element(component.getByText("Cause", { exact: true })).not.toBeInTheDocument();
    await expect
      .element(component.getByText("Required action", { exact: true }))
      .not.toBeInTheDocument();
    await expect
      .element(component.getByText("Message from the remote", { exact: true }))
      .not.toBeInTheDocument();
  });

  test("shows nothing pending, and no paused imports, when no push waits", async () => {
    // GIVEN
    vi.mocked(getRepositoryPushState).mockResolvedValue({
      status: "none",
      statusLabel: "none",
      statusColor: null,
      cause: null,
      causeLabel: null,
      error: null,
      pendingMerges: [],
      queueVersion: 0,
      lastAbandonment: null,
    });

    // WHEN
    const component = await render(<RepositoryPushToRemoteCard repositoryId="repo-1" />);

    // THEN
    await expect.element(component.getByText("Nothing pending")).toBeVisible();
    await expect.element(component.baseElement).not.toHaveTextContent(IMPORTS_PAUSED);
  });

  test("shows why the push state cannot be read", async () => {
    // GIVEN
    vi.mocked(getRepositoryPushState).mockRejectedValue(
      new Error("Cannot read the pending pushes of this repository.")
    );

    // WHEN
    const component = await render(<RepositoryPushToRemoteCard repositoryId="repo-1" />);

    // THEN
    await expect
      .element(component.getByText("Cannot read the pending pushes of this repository."))
      .toBeVisible();
  });
});
