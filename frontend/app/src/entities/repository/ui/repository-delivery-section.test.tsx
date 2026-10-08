import { beforeEach, describe, expect, test, vi } from "vitest";

import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";
import type { DeliveryState } from "@/entities/repository/domain/model/delivery-state";
import { getDeliveryState } from "@/entities/repository/domain/use-cases/get-delivery-state";

import { render } from "../../../../tests/components/render";
import { generateBranch } from "../../../../tests/fake/branch";
import { RepositoryDeliverySection } from "./repository-delivery-section";

vi.mock("@/entities/branches/ui/queries/get-branches.query");
vi.mock("@/entities/repository/domain/use-cases/get-delivery-state");

const IMPORTS_PAUSED =
  "Imports from the remote default branch are paused until the pending pushes clear.";

const refusedPush: DeliveryState = {
  status: "action-required",
  statusLabel: "Action required",
  statusColor: "#f87171",
  cause: "permission",
  causeLabel: "Push refused by the remote",
  error: "remote: error: GH006: Protected branch update failed for refs/heads/main.",
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
};

describe("RepositoryDeliverySection", () => {
  beforeEach(() => {
    vi.resetAllMocks();

    // The selected branch of the render helper is not the default branch.
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
    const component = await render(<RepositoryDeliverySection repositoryId="repo-1" />);

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
    const component = await render(<RepositoryDeliverySection repositoryId="repo-1" />);

    // THEN
    await expect.element(component.getByText("Push to remote")).toBeVisible();
    await expect.element(component.getByText("Push refused by the remote")).toBeVisible();
    await expect
      .element(
        component.getByText("Grant push permission or lift the branch protection, then retry.")
      )
      .toBeVisible();
    await expect.element(component.getByText(IMPORTS_PAUSED)).toBeVisible();
    await expect
      .element(
        component.getByText(
          "remote: error: GH006: Protected branch update failed for refs/heads/main."
        )
      )
      .toBeVisible();
    await expect
      .element(component.getByRole("listitem").first())
      .toHaveTextContent(/^feature-a4b825dc/);
    await expect
      .element(component.getByRole("listitem").last())
      .toHaveTextContent(/^feature-b9daeafb/);
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
    const component = await render(<RepositoryDeliverySection repositoryId="repo-1" />);

    // THEN
    await expect.element(component.getByText("Pending", { exact: true })).toBeVisible();
    await expect.element(component.getByText(IMPORTS_PAUSED)).toBeVisible();
    await expect.element(component.getByText("Cause", { exact: true })).not.toBeInTheDocument();
  });

  test("shows nothing pending, and no paused imports, when no push waits", async () => {
    // GIVEN
    vi.mocked(getDeliveryState).mockResolvedValue({
      status: "none",
      statusLabel: null,
      statusColor: null,
      cause: null,
      causeLabel: null,
      error: null,
      pendingMerges: [],
    });

    // WHEN
    const component = await render(<RepositoryDeliverySection repositoryId="repo-1" />);

    // THEN
    await expect.element(component.getByText("Nothing pending")).toBeVisible();
    await expect.element(component.baseElement).not.toHaveTextContent(IMPORTS_PAUSED);
  });
});
