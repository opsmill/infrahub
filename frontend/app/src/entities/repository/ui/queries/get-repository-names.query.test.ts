import { describe, expect, it } from "vitest";

import { getRepositoryNamesQueryOptions } from "@/entities/repository/ui/queries/get-repository-names.query";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

const params = { branchName: "feature", ids: ["repo-1"] };

describe("getRepositoryNamesQueryOptions", () => {
  it("doesn't ask for names when there is no id", () => {
    expect(getRepositoryNamesQueryOptions({ ...params, ids: [] }).enabled).toBe(false);
  });

  describe("placeholder data", () => {
    const placeholderFor = (branchName: string, previousBranchName: string) => {
      const { placeholderData } = getRepositoryNamesQueryOptions({
        branchName,
        ids: ["repo-2"],
      });
      if (typeof placeholderData !== "function") throw new Error("expected a placeholder function");
      type Args = Parameters<typeof placeholderData>;
      const previousData = { "repo-1": "previous" } as Args[0];
      const previousQuery = {
        queryKey: repositoryQueryKeys.names({ ...params, branchName: previousBranchName }),
      } as unknown as Args[1];
      return { previousData, placeholder: placeholderData(previousData, previousQuery) };
    };

    it("keeps the previous names while the same branch's next lookup loads", () => {
      const { previousData, placeholder } = placeholderFor("feature", "feature");

      expect(placeholder).toBe(previousData);
    });

    it("doesn't show another branch's names while the new branch loads", () => {
      const { placeholder } = placeholderFor("feature", "other-branch");

      expect(placeholder).toBeUndefined();
    });
  });
});
