import { beforeEach, describe, expect, test, vi } from "vitest";

import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type {
  AbandonmentRecord,
  DeliveryState,
} from "@/entities/repository/domain/model/delivery-state";
import { getDeliveryState } from "@/entities/repository/domain/use-cases/get-delivery-state";
import { importCurrentCommit } from "@/entities/repository/domain/use-cases/import-current-commit";

import { render } from "../../../../tests/components/render";
import { generateBranch } from "../../../../tests/fake/branch";
import { generatePermission } from "../../../../tests/fake/permission";
import { RepositoryDeliverySection } from "./repository-delivery-section";

vi.mock("@/entities/branches/ui/queries/get-branches.query");
vi.mock("@/entities/repository/domain/use-cases/get-delivery-state");
vi.mock("@/entities/repository/domain/use-cases/import-current-commit");

const IMPORTS_PAUSED =
  "Imports from the remote default branch are paused until the pending pushes clear.";

const FIRST_COMMIT = "4b825dc642cb6eb9a060e54bf8d69288fbee4904";

const refusedPush: DeliveryState = {
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

const OBJECTS_CAN_STAY =
  "The default branch can hold repository objects that the recorded commit lacks.";
const OBJECTS_CAN_LACK =
  "The default branch can also lack repository objects that the recorded commit holds.";

const lastAbandonment: AbandonmentRecord = {
  format: 1,
  abandoned_at: "2026-10-03T08:00:00.000000+00:00",
  account_name: "alice",
  recorded_commit: "c3d1f0a2b4e5968778695a4b3c2d1e0f9a8b7c6d",
  import_owed_commit: null,
  entries: refusedPush.pendingMerges.slice(0, 1),
};

const nothingPendingAfterAbandonment: DeliveryState = {
  status: "none",
  statusLabel: "none",
  statusColor: null,
  cause: null,
  causeLabel: null,
  error: null,
  pendingMerges: [],
  queueVersion: 3,
  lastAbandonment,
};

const renderSection = (permission: Permission = generatePermission()) =>
  render(<RepositoryDeliverySection repositoryId="repo-1" permission={permission} />);

describe("RepositoryDeliverySection", () => {
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
    vi.mocked(getDeliveryState).mockResolvedValue(refusedPush);

    // WHEN
    const component = await renderSection();

    // THEN
    await expect.element(component.getByText("Action required")).toBeVisible();
    expect(getDeliveryState).toHaveBeenCalledWith({
      repositoryId: "repo-1",
      branchName: "primary",
    });
  });

  test("shows the cause, the required action, the paused imports, the remote's message and the pending merges", async () => {
    // GIVEN
    vi.mocked(getDeliveryState).mockResolvedValue(refusedPush);

    // WHEN
    const component = await renderSection();

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
    await expect
      .element(component.getByRole("listitem").first())
      .toHaveTextContent(/^feature-a4b825dc/);
    await expect
      .element(component.getByRole("listitem").last())
      .toHaveTextContent(/^feature-b9daeafb/);
    await expect.element(component.baseElement).not.toHaveTextContent(FIRST_COMMIT);
  });

  test("shows the paused imports and no cause while the first attempt runs", async () => {
    // GIVEN
    vi.mocked(getDeliveryState).mockResolvedValue({
      ...refusedPush,
      status: "pending",
      statusLabel: "Pending",
      statusColor: "#60a5fa",
      cause: null,
      causeLabel: null,
      error: null,
    });

    // WHEN
    const component = await renderSection();

    // THEN
    await expect.element(component.getByText("Pending", { exact: true })).toBeVisible();
    await expect.element(component.getByText(IMPORTS_PAUSED)).toBeVisible();
    await expect.element(component.getByText("Cause", { exact: true })).not.toBeInTheDocument();
  });

  test("shows nothing pending, and no paused imports, when no push waits", async () => {
    // GIVEN
    vi.mocked(getDeliveryState).mockResolvedValue({
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
    const component = await renderSection();

    // THEN
    await expect.element(component.getByText("Nothing pending")).toBeVisible();
    await expect.element(component.baseElement).not.toHaveTextContent(IMPORTS_PAUSED);
  });

  test("shows why the push state cannot be read", async () => {
    // GIVEN
    vi.mocked(getDeliveryState).mockRejectedValue(
      new Error("Cannot read the pending pushes of this repository.")
    );

    // WHEN
    const component = await renderSection();

    // THEN
    await expect
      .element(component.getByText("Cannot read the pending pushes of this repository."))
      .toBeVisible();
  });

  test("shows the last abandonment, its account, the abandoned merges and the recorded commit", async () => {
    // GIVEN
    vi.mocked(getDeliveryState).mockResolvedValue(nothingPendingAfterAbandonment);

    // WHEN
    const component = await renderSection();

    // THEN
    await expect.element(component.getByText("Nothing pending")).toBeVisible();
    await expect.element(component.getByText("Last abandonment")).toBeVisible();
    await expect.element(component.getByText("alice")).toBeVisible();
    await expect.element(component.getByRole("listitem")).toHaveTextContent(/^feature-a4b825dc/);
    await expect.element(component.getByText("c3d1f0a", { exact: true })).toBeVisible();
    await expect.element(component.getByText(OBJECTS_CAN_STAY)).toBeVisible();
    await expect.element(component.baseElement).not.toHaveTextContent(OBJECTS_CAN_LACK);
  });

  test("also says the default branch can lack objects when the abandonment dropped an import", async () => {
    // GIVEN
    vi.mocked(getDeliveryState).mockResolvedValue({
      ...refusedPush,
      lastAbandonment: { ...lastAbandonment, import_owed_commit: lastAbandonment.recorded_commit },
    });

    // WHEN
    const component = await renderSection();

    // THEN
    await expect.element(component.getByText("Push refused by the remote")).toBeVisible();
    await expect.element(component.getByText(OBJECTS_CAN_STAY)).toBeVisible();
    await expect.element(component.getByText(OBJECTS_CAN_LACK)).toBeVisible();
  });

  test("reimports the current commit on the default branch while another branch is selected", async () => {
    // GIVEN
    vi.mocked(getDeliveryState).mockResolvedValue(nothingPendingAfterAbandonment);
    vi.mocked(importCurrentCommit).mockResolvedValue({ ok: true, taskId: "task-2" });
    const component = await renderSection();

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
    vi.mocked(getDeliveryState).mockResolvedValue(nothingPendingAfterAbandonment);
    vi.mocked(importCurrentCommit).mockRejectedValue(
      new Error("You are not allowed to edit main.")
    );
    const component = await renderSection();

    // WHEN
    await component.getByRole("button", { name: "Reimport current commit" }).click();

    // THEN
    await expect
      .element(
        component.getByText("Error importing current commit: You are not allowed to edit main.")
      )
      .toBeVisible();
  });

  test("disables Reimport current commit without update permission", async () => {
    // GIVEN
    vi.mocked(getDeliveryState).mockResolvedValue(nothingPendingAfterAbandonment);

    // WHEN
    const component = await renderSection(generatePermission({ update: false }));

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Reimport current commit" }))
      .toBeDisabled();
  });
});
