import { describe, expect, it, vi } from "vitest";

import { getBranchActionStateQueryOptions } from "./get-branch-action-state.query";

vi.mock("@/entities/branches/domain/get-branch-action-state", () => ({
  getBranchActionState: vi.fn().mockResolvedValue({ ongoingTaskCount: 0 }),
}));

describe("getBranchActionStateQueryOptions", () => {
  it("builds a stable, object-form query key", () => {
    const opts = getBranchActionStateQueryOptions({
      branchName: "main",
      workflow: ["foo"],
      state: ["RUNNING"],
    });

    expect(opts.queryKey).toEqual([
      "branches",
      "action-state",
      { branchName: "main", workflow: ["foo"], state: ["RUNNING"] },
    ]);
  });
});
