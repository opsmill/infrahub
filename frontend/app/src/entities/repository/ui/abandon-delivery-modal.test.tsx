import { beforeEach, describe, expect, test, vi } from "vitest";

import { queryClient } from "@/shared/api/rest/client";

import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import type { DeliveryState } from "@/entities/repository/domain/model/delivery-state";
import { abandonDelivery } from "@/entities/repository/domain/use-cases/abandon-delivery";

import { render } from "../../../../tests/components/render";
import { generateBranch } from "../../../../tests/fake/branch";
import { AbandonDeliveryModal } from "./abandon-delivery-modal";

vi.mock("@/entities/repository/domain/use-cases/abandon-delivery");
vi.mock("@/entities/branches/ui/queries/get-branches.query");

const conflictingPush: DeliveryState = {
  status: "action-required",
  statusLabel: "Action required",
  statusColor: null,
  cause: "replay-conflict",
  causeLabel: "Conflict on the remote",
  error: null,
  pendingMerges: [
    {
      entry_id: "entry-1",
      source_branch: "feature-a",
      source_commit: "4b825dc642cb6eb9a060e54bf8d69288fbee4904",
      merged_at: "2026-10-02T09:14:03.120000+00:00",
    },
    {
      entry_id: "entry-2",
      source_branch: "feature-b",
      source_commit: "9daeafb9864cf43055ae93beb0afd6c7d144bfa4",
      merged_at: "2026-10-02T10:20:00.000000+00:00",
    },
  ],
  queueVersion: 4,
  lastAbandonment: null,
};

describe("AbandonDeliveryModal", () => {
  const mockOnOpenChange = vi.fn();

  beforeEach(() => {
    vi.resetAllMocks();

    // The selected branch, "test-branch", is not the default branch.
    vi.mocked(useGetBranches).mockReturnValue({
      data: [
        generateBranch({ name: "test-branch" }),
        generateBranch({ name: "primary", is_default: true }),
      ],
    } as unknown as ReturnType<typeof useGetBranches>);

    vi.mocked(abandonDelivery).mockResolvedValue({ ok: true, taskId: "task-1" });
  });

  const renderModal = (deliveryState = conflictingPush) =>
    render(
      <AbandonDeliveryModal
        repositoryId="repo-1"
        deliveryState={deliveryState}
        isOpen
        onOpenChange={mockOnOpenChange}
      />
    );

  test("lists the pending merges it abandons and says what stays", async () => {
    // GIVEN
    const deliveryState = conflictingPush;

    // WHEN
    const component = await renderModal(deliveryState);

    // THEN
    await expect
      .element(component.getByRole("heading", { name: "Abandon pending push" }))
      .toBeVisible();
    await expect
      .element(component.getByRole("listitem").first())
      .toHaveTextContent(/^feature-a4b825dc/);
    await expect
      .element(component.getByRole("listitem").last())
      .toHaveTextContent(/^feature-b9daeafb/);
    await expect
      .element(
        component.getByText("Nothing is removed from the remote, and no remote branch is deleted.")
      )
      .toBeVisible();
    await expect
      .element(
        component.getByText(
          "Repository objects of the abandoned merges can stay on the default branch until the current commit is reimported."
        )
      )
      .toBeVisible();
  });

  test("abandons the version the user read on the default branch while another branch is selected", async () => {
    // GIVEN
    const component = await renderModal();

    // WHEN
    await component.getByRole("button", { name: "Abandon" }).click();

    // THEN
    await vi.waitFor(() =>
      expect(abandonDelivery).toHaveBeenCalledWith({
        branchName: "primary",
        repositoryId: "repo-1",
        queueVersion: 4,
      })
    );
  });

  test("links to the task and closes when the abandonment starts", async () => {
    // GIVEN
    const component = await renderModal();

    // WHEN
    await component.getByRole("button", { name: "Abandon" }).click();

    // THEN
    await expect
      .element(component.getByText("Abandonment of the pending pushes started."))
      .toBeVisible();
    await expect
      .element(component.getByRole("link", { name: "View task" }))
      .toHaveAttribute("href", "/tasks/task-1");
    expect(mockOnOpenChange).toHaveBeenCalledWith(false);
  });

  test("shows the refusal message, closes and reloads the state when the pending pushes changed", async () => {
    // GIVEN
    const invalidateQueriesSpy = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockResolvedValue(undefined);
    vi.mocked(abandonDelivery).mockRejectedValue(
      new Error(
        "The pending pushes of repository repo-a changed since version 4; reload and try again."
      )
    );
    const component = await renderModal();

    // WHEN
    await component.getByRole("button", { name: "Abandon" }).click();

    // THEN
    await expect
      .element(
        component.getByText(
          "Error abandoning the pending pushes: The pending pushes of repository repo-a changed since version 4; reload and try again."
        )
      )
      .toBeVisible();
    await vi.waitFor(() => expect(mockOnOpenChange).toHaveBeenCalledWith(false));
    expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: objectQueryKeys.all });
  });

  test("closes without abandoning on Cancel", async () => {
    // GIVEN
    const component = await renderModal();

    // WHEN
    await component.getByRole("button", { name: "Cancel" }).click();

    // THEN
    expect(mockOnOpenChange).toHaveBeenCalledWith(false);
    expect(abandonDelivery).not.toHaveBeenCalled();
  });
});
