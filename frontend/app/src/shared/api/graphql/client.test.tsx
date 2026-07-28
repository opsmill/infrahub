import { CombinedError, gql } from "@urql/core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ERROR_CODES } from "@/shared/api/errors";
import { PRIORITY_HEADER } from "@/shared/api/priority";
import { queryClient } from "@/shared/api/rest/client";
import { CONFIG } from "@/shared/config/config";

import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from "@/entities/authentication/api/token-storage";
import { __navigation } from "@/entities/authentication/domain/use-cases/redirect-to-login";

import { graphqlClient } from "./client";
import { handleGraphQLErrors } from "./error-handling";

// Build a CombinedError carrying a single catalogue-coded GraphQL error.
function combinedError(code: string, message = "boom") {
  return new CombinedError({
    graphQLErrors: [{ message, extensions: { code, http_status: 401, data: {} } }],
  });
}

describe("graphqlClient — endpoint targeting", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  const PING = gql`
    query Ping {
      __typename
    }
  `;

  beforeEach(() => {
    fetchSpy = vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify({ data: { __typename: "Query" } }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
    );
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("targets the default branch when the operation declares no context", async () => {
    // WHEN
    await graphqlClient.query({ query: PING });

    // THEN
    expect(fetchSpy.mock.calls[0]?.[0]).toBe(CONFIG.GRAPHQL_URL());
  });

  it("targets the branch and point in time the operation declares", async () => {
    // GIVEN
    const date = new Date("2026-01-01T00:00:00.000Z");

    // WHEN
    await graphqlClient.query({ query: PING, context: { branch: "feature", date } });

    // THEN
    expect(fetchSpy.mock.calls[0]?.[0]).toBe(CONFIG.GRAPHQL_URL("feature", date));
  });

  it("stamps X-Priority: high on every operation", async () => {
    // WHEN
    await graphqlClient.query({ query: PING });

    // THEN
    const init = fetchSpy.mock.calls[0]?.[1] as RequestInit;
    expect(new Headers(init.headers).get(PRIORITY_HEADER)).toBe("high");
  });
});

describe("handleGraphQLErrors — catalogue routing", () => {
  let assignSpy: ReturnType<typeof vi.fn>;
  let originalAssign: typeof __navigation.assign;

  beforeEach(() => {
    originalAssign = __navigation.assign;
    assignSpy = vi.fn();
    __navigation.assign = assignSpy as unknown as typeof __navigation.assign;
  });

  afterEach(() => {
    __navigation.assign = originalAssign;
    localStorage.clear();
  });

  it("redirects to /login on a persistent TOKEN_EXPIRED", () => {
    // WHEN
    handleGraphQLErrors(combinedError(ERROR_CODES.TOKEN_EXPIRED));

    // THEN
    expect(assignSpy).toHaveBeenCalledOnce();
  });

  it("redirects to /login on AUTHENTICATION_REQUIRED", () => {
    // WHEN
    handleGraphQLErrors(combinedError(ERROR_CODES.AUTHENTICATION_REQUIRED));

    // THEN
    expect(assignSpy).toHaveBeenCalledOnce();
  });

  it("stays silent on PERMISSION_DENIED (no redirect, no override call)", () => {
    // GIVEN
    const processErrorMessage = vi.fn();

    // WHEN
    handleGraphQLErrors(combinedError(ERROR_CODES.PERMISSION_DENIED), { processErrorMessage });

    // THEN
    expect(assignSpy).not.toHaveBeenCalled();
    expect(processErrorMessage).not.toHaveBeenCalled();
  });

  it("routes a generic error through the caller's processErrorMessage override", () => {
    // GIVEN
    const processErrorMessage = vi.fn();

    // WHEN — UNDEFINED_ERROR is the generic/unknown path
    handleGraphQLErrors(combinedError(ERROR_CODES.UNDEFINED_ERROR, "nope"), {
      processErrorMessage,
    });

    // THEN
    expect(processErrorMessage).toHaveBeenCalledWith("nope");
    expect(assignSpy).not.toHaveBeenCalled();
  });

  it("does nothing when there is no error", () => {
    // GIVEN
    const processErrorMessage = vi.fn();

    // WHEN
    handleGraphQLErrors(undefined, { processErrorMessage });

    // THEN
    expect(processErrorMessage).not.toHaveBeenCalled();
    expect(assignSpy).not.toHaveBeenCalled();
  });
});

// Integration: drive the real client + exchange chain through a stubbed global
// fetch to prove the refresh contract (one refresh + one replay, then bail) and
// the result-shape invariants.
describe("graphqlClient — token refresh integration", () => {
  let assignSpy: ReturnType<typeof vi.fn>;
  let originalAssign: typeof __navigation.assign;
  let fetchQuerySpy: ReturnType<typeof vi.spyOn>;
  let fetchSpy: ReturnType<typeof vi.fn>;

  const PING = gql`
    query Ping {
      __typename
    }
  `;

  const PING_MUTATION = gql`
    mutation Ping {
      __typename
    }
  `;

  function jsonResponse(body: unknown) {
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  const tokenExpiredBody = {
    data: null,
    errors: [
      {
        message: "Token expired",
        extensions: { code: ERROR_CODES.TOKEN_EXPIRED, http_status: 401, data: {} },
      },
    ],
  };

  beforeEach(() => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "old-token");
    localStorage.setItem(REFRESH_TOKEN_KEY, "old-refresh");
    originalAssign = __navigation.assign;
    assignSpy = vi.fn();
    __navigation.assign = assignSpy as unknown as typeof __navigation.assign;
    fetchQuerySpy = vi.spyOn(queryClient, "fetchQuery");
    fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    __navigation.assign = originalAssign;
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("sends queries as POST (backend /graphql rejects GET → SPA fallback HTML)", async () => {
    // GIVEN a successful query
    fetchSpy.mockResolvedValueOnce(jsonResponse({ data: { __typename: "Query" } }));

    // WHEN
    await graphqlClient.query({ query: PING });

    // THEN the request is POST — NOT GET (urql's `within-url-limit` default would
    // GET small queries, which the backend answers with index.html)
    const init = fetchSpy.mock.calls[0]?.[1] as RequestInit | undefined;
    expect(init?.method).toBe("POST");
  });

  it("injects __typename into selections (Apollo InMemoryCache parity)", async () => {
    // GIVEN a query whose selections omit __typename (as the dynamic object
    // queries do — they relied on Apollo auto-adding it)
    fetchSpy.mockResolvedValueOnce(jsonResponse({ data: {} }));

    // WHEN
    await graphqlClient.query({
      query: gql`
        {
          InfraDevice {
            edges {
              node {
                id
              }
            }
          }
        }
      `,
    });

    // THEN the request body's query carries __typename (added by formatDocument)
    const body = JSON.parse((fetchSpy.mock.calls[0]?.[1] as RequestInit).body as string);
    expect(body.query).toContain("__typename");
  });

  it("attaches the bearer token when an access token is present", async () => {
    // GIVEN
    fetchSpy.mockResolvedValueOnce(jsonResponse({ data: {} }));

    // WHEN
    await graphqlClient.query({ query: PING });

    // THEN
    const init = fetchSpy.mock.calls[0]?.[1] as RequestInit;
    expect(new Headers(init.headers).get("authorization")).toBe("Bearer old-token");
  });

  it("omits the bearer token when no access token is present", async () => {
    // GIVEN
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    fetchSpy.mockResolvedValueOnce(jsonResponse({ data: {} }));

    // WHEN
    await graphqlClient.query({ query: PING });

    // THEN
    const init = fetchSpy.mock.calls[0]?.[1] as RequestInit;
    expect(new Headers(init.headers).get("authorization")).toBeNull();
  });

  it("bails to /login when the refresh throws", async () => {
    // GIVEN
    fetchSpy.mockImplementation(() => Promise.resolve(jsonResponse(tokenExpiredBody)));
    fetchQuerySpy.mockRejectedValue(new Error("refresh failed"));

    // WHEN
    await graphqlClient.query({ query: PING }).catch(() => {});

    // THEN
    expect(assignSpy).toHaveBeenCalled();
  });

  it("refreshes once and replays successfully on TOKEN_EXPIRED", async () => {
    // GIVEN a first response that is TOKEN_EXPIRED, a successful refresh, and a
    // second (replayed) response that succeeds.
    fetchSpy
      .mockResolvedValueOnce(jsonResponse(tokenExpiredBody))
      .mockResolvedValueOnce(jsonResponse({ data: { __typename: "Query" } }));
    fetchQuerySpy.mockResolvedValue({ access_token: "new-token", refresh_token: "new-refresh" });

    // WHEN
    const result = await graphqlClient.query({ query: PING });

    // THEN — data returned, exactly one refresh, exactly one replay, no redirect
    expect(result.data).toEqual({ __typename: "Query" });
    expect(result.errors).toBeUndefined();
    expect(fetchQuerySpy).toHaveBeenCalledOnce();
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(assignSpy).not.toHaveBeenCalled();
  });

  it("bails to /login when TOKEN_EXPIRED persists after the single replay", async () => {
    // GIVEN every response is TOKEN_EXPIRED and the refresh succeeds. Use a
    // fresh Response per call — a Response body stream can only be read once.
    fetchSpy.mockImplementation(() => Promise.resolve(jsonResponse(tokenExpiredBody)));
    fetchQuerySpy.mockResolvedValue({ access_token: "new-token", refresh_token: "new-refresh" });

    // WHEN
    const querying = graphqlClient.query({ query: PING });

    // THEN — only ONE replay (2 fetches), one refresh, and the persistent expiry
    // routes to /login.
    await expect(querying).rejects.toThrow("Token expired");
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(fetchQuerySpy).toHaveBeenCalledOnce();
    expect(assignSpy).toHaveBeenCalled();
  });

  it("rejects a query on GraphQL errors even when the response carries data", async () => {
    // GIVEN a response with both data and a (non-auth) error.
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({
        data: { __typename: "Query" },
        errors: [
          {
            message: "partial",
            extensions: { code: ERROR_CODES.UNDEFINED_ERROR, http_status: 500, data: {} },
          },
        ],
      })
    );

    // WHEN
    const querying = graphqlClient.query({
      query: PING,
      context: { processErrorMessage: () => {} },
    });

    // THEN — callers never have to decide what a half-failed read means
    await expect(querying).rejects.toThrow("partial");
  });

  // Both queries and mutations reject when the response carries GraphQL errors: use-cases await a mutation without checking
  it("rejects when a mutation responds with GraphQL errors", async () => {
    // GIVEN a mutation whose response carries a GraphQL error
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({
        data: null,
        errors: [
          {
            message: "Cannot delete Device 'x'.",
            extensions: { code: ERROR_CODES.UNDEFINED_ERROR, http_status: 500, data: {} },
          },
        ],
      })
    );

    // WHEN
    const mutating = graphqlClient.mutate({
      mutation: PING_MUTATION,
      context: { processErrorMessage: () => {} },
    });

    // THEN the caller sees a rejection carrying the backend message, unprefixed
    await expect(mutating).rejects.toThrow("Cannot delete Device 'x'.");
  });
});
