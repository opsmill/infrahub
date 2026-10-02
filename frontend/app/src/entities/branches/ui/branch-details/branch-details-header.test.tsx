import { beforeEach, describe, expect, test, vi } from "vitest";

import { BranchStatus } from "@/shared/api/graphql/generated/types";

import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import { NodeMetadataPopover } from "@/entities/nodes/object/ui/metadata/node-metadata-popover";
import { RefreshButton } from "@/entities/nodes/object/ui/object-details/refresh-button";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

import { render } from "../../../../../tests/components/render";
import { generateBranch } from "../../../../../tests/fake/branch";
import { BranchDetailsHeader } from "./branch-details-header";

vi.mock("@/entities/nodes/object/ui/metadata/node-metadata-popover", () => ({
  NodeMetadataPopover: vi.fn(() => <button type="button">Metadata</button>),
}));
vi.mock("@/entities/nodes/object/ui/object-details/refresh-button", () => ({
  RefreshButton: vi.fn(() => <button type="button">Refresh data</button>),
}));

describe("BranchDetailsHeader", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("renders name, copy, metadata, status badge and refresh in that order", async () => {
    // GIVEN
    const branch = generateBranch({ name: "feature-x", status: BranchStatus.NEED_REBASE });

    // WHEN
    const component = await render(<BranchDetailsHeader branch={branch} />);

    // THEN
    const row = component.getByTestId("branch-details-header");
    await expect.element(row).toBeVisible();
    const parts = Array.from(row.element().children).map((el) => el.textContent);
    expect(parts).toEqual(["feature-x", "", "Metadata", "Rebase needed", "Refresh data"]);
    await expect
      .element(component.getByRole("heading", { level: 1, name: "feature-x" }))
      .toHaveAttribute("title", "feature-x");
    expect(NodeMetadataPopover).toHaveBeenCalledWith(
      expect.objectContaining({ objectKind: "InfrahubBranch", objectId: branch.id }),
      undefined
    );
  });

  test("gives the copy button an accessible name", async () => {
    // GIVEN
    const branch = generateBranch();

    // WHEN
    const component = await render(<BranchDetailsHeader branch={branch} />);

    // THEN
    await expect.element(component.getByRole("button", { name: "Copy branch name" })).toBeVisible();
  });

  test("shows the default badge instead of the status badge on the default branch", async () => {
    // GIVEN
    const branch = generateBranch({
      name: "main",
      is_default: true,
      status: BranchStatus.NEED_REBASE,
    });

    // WHEN
    const component = await render(<BranchDetailsHeader branch={branch} />);

    // THEN
    await expect.element(component.getByText("default", { exact: true })).toBeVisible();
    expect(component.getByText("Rebase needed").query()).toBeNull();
  });

  test("shows the description when the branch has one", async () => {
    // GIVEN
    const branch = generateBranch({ description: "Upgrade the platform" });

    // WHEN
    const component = await render(<BranchDetailsHeader branch={branch} />);

    // THEN
    await expect.element(component.getByText("Upgrade the platform")).toBeVisible();
  });

  test("renders no description paragraph when the branch has none", async () => {
    // GIVEN
    const branch = generateBranch({ description: "" });

    // WHEN
    const component = await render(<BranchDetailsHeader branch={branch} />);

    // THEN
    await expect.element(component.getByTestId("branch-details-header")).toBeVisible();
    expect(component.container.querySelector("p")).toBeNull();
  });

  test("refreshes branches, repositories and tasks", async () => {
    // GIVEN
    const branch = generateBranch();

    // WHEN
    await render(<BranchDetailsHeader branch={branch} />);

    // THEN
    expect(RefreshButton).toHaveBeenCalledWith(
      expect.objectContaining({
        className: "ml-auto",
        queryKeys: [branchesQueryKeys.all, repositoryQueryKeys.all, tasksQueryKeys.all],
      }),
      undefined
    );
  });
});
