import { CombinedError } from "@urql/core";
import { GraphQLError } from "graphql";
import { describe, expect, it } from "vitest";

import { BranchGitStatusError } from "@/entities/branch-git-status/domain/model/branch-git-status";
import { toBranchGitStatusError } from "@/entities/branch-git-status/domain/rules/to-branch-git-status-error";

const graphQLFailure = (...codes: string[]) =>
  new Error("nope", {
    cause: new CombinedError({
      graphQLErrors: codes.map(
        (code) => new GraphQLError(code, { extensions: { code, http_status: 403 } })
      ),
    }),
  });

describe("toBranchGitStatusError", () => {
  it("maps a permission denial to the PERMISSION_DENIED code", () => {
    expect(toBranchGitStatusError(graphQLFailure("PERMISSION_DENIED"), "fallback").code).toBe(
      "PERMISSION_DENIED"
    );
  });

  it.each([
    {
      name: "a denial mixed with another failure",
      error: graphQLFailure("PERMISSION_DENIED", "NODE_NOT_FOUND"),
    },
    { name: "another catalogue failure", error: graphQLFailure("NODE_NOT_FOUND") },
    { name: "a network failure", error: new TypeError("Failed to fetch") },
  ])("maps $name to the UNKNOWN code", ({ error }) => {
    expect(toBranchGitStatusError(error, "fallback").code).toBe("UNKNOWN");
  });

  it("keeps the failure's message and the failure itself as the cause", () => {
    // GIVEN
    const networkError = new TypeError("Failed to fetch");

    // WHEN
    const error = toBranchGitStatusError(networkError, "fallback");

    // THEN
    expect(error).toBeInstanceOf(BranchGitStatusError);
    expect(error.message).toBe("Failed to fetch");
    expect(error.cause).toBe(networkError);
  });

  it("uses the fallback message when the failure is not an Error", () => {
    expect(toBranchGitStatusError("boom", "Failed to load").message).toBe("Failed to load");
  });
});
