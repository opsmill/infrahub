import { gql } from "@urql/core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { graphqlClient } from "./client";

// Guards against urql merging concurrent identical operations that target different endpoints.
describe("concurrent identical query across endpoints", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  const SAME_QUERY = gql`
    query SameQuery {
      __typename
    }
  `;

  beforeEach(() => {
    // Echo the endpoint back so each caller can be matched to the URL it targeted.
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
    // WHEN
    const [a, b] = await Promise.all([
      graphqlClient.query({ query: SAME_QUERY, context: { branch: "branch-a" } }),
      graphqlClient.query({ query: SAME_QUERY, context: { branch: "branch-b" } }),
    ]);

    // THEN
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(a.data).toEqual({ __typename: "branch-a" });
    expect(b.data).toEqual({ __typename: "branch-b" });
  });

  it("fires a distinct request per point-in-time on the same branch", async () => {
    // GIVEN
    const early = new Date("2026-01-01T00:00:00.000Z");
    const late = new Date("2026-06-01T00:00:00.000Z");

    // WHEN
    const [a, b] = await Promise.all([
      graphqlClient.query({ query: SAME_QUERY, context: { branch: "main", date: early } }),
      graphqlClient.query({ query: SAME_QUERY, context: { branch: "main", date: late } }),
    ]);

    // THEN
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(a.data).toEqual({ __typename: `main@${early.toISOString()}` });
    expect(b.data).toEqual({ __typename: `main@${late.toISOString()}` });
  });

  it("still merges two identical concurrent queries on the same endpoint", async () => {
    // WHEN
    const [a, b] = await Promise.all([
      graphqlClient.query({ query: SAME_QUERY, context: { branch: "branch-a" } }),
      graphqlClient.query({ query: SAME_QUERY, context: { branch: "branch-a" } }),
    ]);

    // THEN
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(a.data).toEqual({ __typename: "branch-a" });
    expect(b.data).toEqual({ __typename: "branch-a" });
  });
});
