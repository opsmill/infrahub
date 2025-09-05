import { beforeEach, describe, expect, it, vi } from "vitest";

import { store } from "@/shared/stores";

import { getCurrentBranchName } from "@/entities/branches/domain/get-current-branch";
import { currentBranchAtom } from "@/entities/branches/stores";

import { generateBranch } from "../../../../tests/fake/branch";

describe("getCurrentBranchName - test", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should return the current branch name when branch exists", () => {
    const mockBranch = generateBranch({ name: "feature/test-branch" });
    vi.spyOn(store, "get").mockReturnValue(mockBranch);

    const result = getCurrentBranchName();

    expect(result).toBe("feature/test-branch");
    expect(store.get).toHaveBeenCalledWith(currentBranchAtom);
  });

  it("should return default branch name when no current branch exists", () => {
    vi.spyOn(store, "get").mockReturnValue(null);

    const result = getCurrentBranchName();

    expect(result).toBe("main");
    expect(store.get).toHaveBeenCalledWith(currentBranchAtom);
  });
});
