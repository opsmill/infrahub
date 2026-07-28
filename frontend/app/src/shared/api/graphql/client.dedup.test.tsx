import { gql } from "@urql/core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { graphqlClient } from "./client";

// Regression guard for the cross-branch dedup hazard. urql's Client dedups
// concurrent operations by hash(query, variables), IGNORING context — but this
// app carries branch/date in context.url, not variables. Without the request-key
// fix in `graphqlClient.tsx` (`keyedQueryRequest`), two concurrent identical
// query+vars on DIFFERENT branches share one network request and both receive
// one branch's data. This test proves the fix keeps them distinct.
describe("cross-branch concurrent identical query dedup guard", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  const SAME_QUERY = gql`
    query SameQuery {
      __typename
    }
  `;

  beforeEach(() => {
    // Echo the requested branch back in the response so each caller can be
    // matched to the URL it targeted.
    fetchSpy = vi.fn((url: string) => {
      const branch = url.split("/graphql/")[1]?.split("?")[0] ?? "?";
      return Promise.resolve(
        new Response(JSON.stringify({ data: { __typename: branch } }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );
    });
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("fires a distinct request per branch for concurrent identical query+variables", async () => {
    // WHEN two identical queries run concurrently, differing only by branch
    const [a, b] = await Promise.all([
      graphqlClient.query({ query: SAME_QUERY, context: { branch: "branch-a" } }),
      graphqlClient.query({ query: SAME_QUERY, context: { branch: "branch-b" } }),
    ]);

    // THEN each resolves with its OWN branch's data and two fetches were made
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(a.data).toEqual({ __typename: "branch-a" });
    expect(b.data).toEqual({ __typename: "branch-b" });
  });
});
