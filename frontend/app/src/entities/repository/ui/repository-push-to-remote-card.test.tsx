import { beforeEach, describe, expect, test, vi } from "vitest";

import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";
import { getObjectPermissions } from "@/entities/permission/domain/use-cases/get-object-permissions";
import { useHasGlobalPermission } from "@/entities/permission/ui/queries/has-global-permission.query";
import type {
  AbandonedPush,
  RepositoryPushState,
} from "@/entities/repository/domain/model/repository-push-state";
import { getRepositoryPushState } from "@/entities/repository/domain/use-cases/get-repository-push-state";
import { importCurrentCommit } from "@/entities/repository/domain/use-cases/import-current-commit";

import { render } from "../../../../tests/components/render";
import { generateBranch } from "../../../../tests/fake/branch";
import { generatePermission } from "../../../../tests/fake/permission";
import { RepositoryPushToRemoteCard } from "./repository-push-to-remote-card";

vi.mock("@/entities/branches/ui/queries/get-branches.query");
vi.mock("@/entities/repository/domain/use-cases/get-repository-push-state");
vi.mock("@/entities/repository/domain/use-cases/import-current-commit");
vi.mock("@/entities/permission/ui/queries/has-global-permission.query");
vi.mock("@/entities/permission/domain/use-cases/get-object-permissions");

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
  lastAbandonedPush: null,
};

const OBJECTS_CAN_STAY =
  "The default branch can hold repository objects that the recorded commit lacks.";
const OBJECTS_CAN_LACK =
  "The default branch can also lack repository objects that the recorded commit holds.";

const lastAbandonedPush: AbandonedPush = {
  format: 1,
  abandoned_at: "2026-10-03T08:00:00.000000+00:00",
  account_name: "alice",
  recorded_commit: "c3d1f0a2b4e5968778695a4b3c2d1e0f9a8b7c6d",
  import_owed_commit: null,
  entries: refusedPush.pendingMerges.slice(0, 1),
};

const nothingPendingAfterAbandon: RepositoryPushState = {
  status: "none",
  statusLabel: "none",
  statusColor: null,
  cause: null,
  causeLabel: null,
  error: null,
  pendingMerges: [],
  queueVersion: 3,
  lastAbandonedPush,
};

const renderCard = () => render(<RepositoryPushToRemoteCard repositoryId="repo-1" />);

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
    vi.mocked(useHasGlobalPermission).mockReturnValue({
      data: true,
    } as unknown as ReturnType<typeof useHasGlobalPermission>);
    vi.mocked(getObjectPermissions).mockResolvedValue(generatePermission());
  });

  test("reads the push state from the default branch while another branch is selected", async () => {
    // GIVEN
    vi.mocked(getRepositoryPushState).mockResolvedValue(refusedPush);

    // WHEN
    const component = await renderCard();

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
    const component = await renderCard();

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
    const component = await renderCard();

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
    const component = await renderCard();

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
      lastAbandonedPush: null,
    });

    // WHEN
    const component = await renderCard();

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
    const component = await renderCard();

    // THEN
    await expect
      .element(component.getByText("Cannot read the pending pushes of this repository."))
      .toBeVisible();
  });

  test("shows the last abandoned push, its account, the abandoned merges and the recorded commit", async () => {
    // GIVEN
    vi.mocked(getRepositoryPushState).mockResolvedValue(nothingPendingAfterAbandon);

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("Nothing pending")).toBeVisible();
    await expect.element(component.getByText("Last abandoned push")).toBeVisible();
    await expect.element(component.getByText("alice")).toBeVisible();
    await expect.element(component.getByText("feature-a", { exact: true })).toBeVisible();
    await expect.element(component.getByText("4b825dc", { exact: true })).toBeVisible();
    await expect.element(component.getByText("c3d1f0a", { exact: true })).toBeVisible();
    await expect.element(component.getByText(OBJECTS_CAN_STAY)).toBeVisible();
    await expect.element(component.baseElement).not.toHaveTextContent(OBJECTS_CAN_LACK);
  });

  test("also says the default branch can lack objects when abandoning dropped an import", async () => {
    // GIVEN
    vi.mocked(getRepositoryPushState).mockResolvedValue({
      ...refusedPush,
      lastAbandonedPush: {
        ...lastAbandonedPush,
        import_owed_commit: lastAbandonedPush.recorded_commit,
      },
    });

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("Push refused by the remote")).toBeVisible();
    await expect.element(component.getByText(OBJECTS_CAN_STAY)).toBeVisible();
    await expect.element(component.getByText(OBJECTS_CAN_LACK)).toBeVisible();
  });

  test("offers no reimport while pushes are pending, since the backend refuses it", async () => {
    // GIVEN
    vi.mocked(getRepositoryPushState).mockResolvedValue({ ...refusedPush, lastAbandonedPush });

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("Last abandoned push")).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Reimport current commit" }))
      .not.toBeInTheDocument();
  });

  test("reimports the current commit on the default branch while another branch is selected", async () => {
    // GIVEN
    vi.mocked(getRepositoryPushState).mockResolvedValue(nothingPendingAfterAbandon);
    vi.mocked(importCurrentCommit).mockResolvedValue({ ok: true, taskId: "task-2" });
    const component = await renderCard();

    // WHEN
    await component.getByRole("button", { name: "Reimport current commit" }).click();

    // THEN
    await vi.waitFor(() =>
      expect(importCurrentCommit).toHaveBeenCalledWith({
        branchName: "primary",
        repositoryId: "repo-1",
      })
    );
    await expect
      .element(component.getByRole("link", { name: "View task" }))
      .toHaveAttribute("href", "/tasks/task-2");
  });

  test("shows why the reimport is refused", async () => {
    // GIVEN
    vi.mocked(getRepositoryPushState).mockResolvedValue(nothingPendingAfterAbandon);
    vi.mocked(importCurrentCommit).mockRejectedValue(
      new Error("You are not allowed to edit main.")
    );
    const component = await renderCard();

    // WHEN
    await component.getByRole("button", { name: "Reimport current commit" }).click();

    // THEN
    await expect
      .element(
        component.getByText("Error importing current commit: You are not allowed to edit main.")
      )
      .toBeVisible();
  });

  test("enables Reimport on the default branch from the update permission on the default branch while another branch is selected", async () => {
    // GIVEN
    vi.mocked(getRepositoryPushState).mockResolvedValue(nothingPendingAfterAbandon);

    // WHEN
    const component = await renderCard();

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Reimport current commit" }))
      .toBeEnabled();
    expect(getObjectPermissions).toHaveBeenCalledWith(
      expect.objectContaining({ kind: "CoreRepository", branchName: "primary" })
    );
  });

  test("disables Reimport on the default branch without update permission on the default branch", async () => {
    // GIVEN
    vi.mocked(getRepositoryPushState).mockResolvedValue(nothingPendingAfterAbandon);
    vi.mocked(getObjectPermissions).mockResolvedValue(generatePermission({ update: false }));

    // WHEN
    const component = await renderCard();

    // THEN
    await vi.waitFor(() => expect(getObjectPermissions).toHaveBeenCalled());
    await expect
      .element(component.getByRole("button", { name: "Reimport current commit" }))
      .toBeDisabled();
  });

  test("disables Reimport on the default branch without the permission to edit the default branch", async () => {
    // GIVEN
    vi.mocked(getRepositoryPushState).mockResolvedValue(nothingPendingAfterAbandon);
    vi.mocked(useHasGlobalPermission).mockReturnValue({
      data: false,
    } as unknown as ReturnType<typeof useHasGlobalPermission>);

    // WHEN
    const component = await renderCard();

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Reimport current commit" }))
      .toBeDisabled();
  });
});
