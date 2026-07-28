import { gql } from "@urql/core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { graphqlClient } from "./client";

// Regression guard for the cross-endpoint merge hazard. urql's Client merges
// concurrent operations by hash(query, variables), IGNORING the URL — but this
// app carries branch/date in the URL, not in variables. Sharing one client
// across endpoints makes two concurrent identical query+vars on DIFFERENT
// branches share one network request, with both callers receiving one branch's
// data. These tests prove the per-endpoint clients keep them distinct.
describe("concurrent identical query across endpoints", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  const SAME_QUERY = gql`
    query SameQuery {
      __typename
    }
  `;

  beforeEach(() => {
    // Echo the requested endpoint back in the response so each caller can be
    // matched to the URL it targeted.
    fetchSpy = vi.fn((url: string) => {
      const [branch, at] = url.split("/graphql/")[1]?.split("?at=") ?? ["?"];
      return Promise.resolve(
        new Response(JSON.stringify({ data: { __typename: at ? `${branch}@${at}` : branch } }), {
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

  it("fires a distinct request per point-in-time on the same branch", async () => {
    // GIVEN two points in time on one branch
    const early = new Date("2026-01-01T00:00:00.000Z");
    const late = new Date("2026-06-01T00:00:00.000Z");

    // WHEN two identical queries run concurrently, differing only by date
    const [a, b] = await Promise.all([
      graphqlClient.query({ query: SAME_QUERY, context: { branch: "main", date: early } }),
      graphqlClient.query({ query: SAME_QUERY, context: { branch: "main", date: late } }),
    ]);

    // THEN each resolves with its OWN point-in-time data and two fetches were made
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(a.data).toEqual({ __typename: `main@${early.toISOString()}` });
    expect(b.data).toEqual({ __typename: `main@${late.toISOString()}` });
  });

  it("still merges two identical concurrent queries on the same endpoint", async () => {
    // WHEN the same query runs twice concurrently against one endpoint
    const [a, b] = await Promise.all([
      graphqlClient.query({ query: SAME_QUERY, context: { branch: "branch-a" } }),
      graphqlClient.query({ query: SAME_QUERY, context: { branch: "branch-a" } }),
    ]);

    // THEN one request served both callers
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(a.data).toEqual({ __typename: "branch-a" });
    expect(b.data).toEqual({ __typename: "branch-a" });
  });
});
