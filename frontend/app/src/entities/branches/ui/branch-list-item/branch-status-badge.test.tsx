import { describe, expect, it } from "vitest";

import { BranchStatus } from "@/shared/api/graphql/generated/types";

import { BranchStatusBadge } from "@/entities/branches/ui/branch-list-item/branch-status-badge";

import { render } from "../../../../../tests/components/render";

describe("BranchStatusBadge", () => {
  it("names a branch that is being merged", async () => {
    // WHEN
    const component = await render(<BranchStatusBadge status={BranchStatus.MERGING} />);

    // THEN
    await expect.element(component.getByText("Merging", { exact: true })).toBeVisible();
  });

  it("names a branch whose merge failed", async () => {
    // WHEN
    const component = await render(<BranchStatusBadge status={BranchStatus.MERGE_FAILED} />);

    // THEN
    await expect.element(component.getByText("Merge failed", { exact: true })).toBeVisible();
  });
});
