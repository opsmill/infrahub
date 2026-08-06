import { CombinedError, gql } from "@urql/core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ERROR_CODES } from "@/shared/api/errors";
import { PRIORITY_HEADER } from "@/shared/api/priority";
import { queryClient } from "@/shared/api/rest/client";
import { INFRAHUB_API_SERVER_URL } from "@/shared/config/config";

import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from "@/entities/authentication/api/token-storage";
import { __navigation } from "@/entities/authentication/domain/use-cases/redirect-to-login";

import { graphqlClient } from "./client";
import { handleGraphQLErrors } from "./error-handling";

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

  it("omits the branch segment when the operation declares no context", async () => {
    // WHEN
    await graphqlClient.query({ query: PING });

    // THEN
    expect(fetchSpy.mock.calls[0]?.[0]).toBe(`${INFRAHUB_API_SERVER_URL}/graphql`);
  });

  it("targets the branch and point in time the operation declares", async () => {
    // GIVEN
    const date = new Date("2026-01-01T00:00:00.000Z");

    // WHEN
    await graphqlClient.query({ query: PING, context: { branch: "feature", date } });

    // THEN
    expect(fetchSpy.mock.calls[0]?.[0]).toBe(
      `${INFRAHUB_API_SERVER_URL}/graphql/feature?at=2026-01-01T00:00:00.000Z`
    );
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

    // WHEN
    handleGraphQLErrors(combinedError(ERROR_CODES.UNDEFINED_ERROR, "nope"), {
      processErrorMessage,
    });

    // THEN
    expect(processErrorMessage).toHaveBeenCalledWith("nope");
    expect(assignSpy).not.toHaveBeenCalled();
  });

  it("still redirects when an unrouted error precedes AUTHENTICATION_REQUIRED", () => {
    // GIVEN
    const processErrorMessage = vi.fn();
    const error = new CombinedError({
      graphQLErrors: [
        {
          message: "boom",
          extensions: { code: ERROR_CODES.NODE_NOT_FOUND, http_status: 404, data: {} },
        },
        { message: "gap", extensions: { code: "NOT_IN_CATALOGUE", http_status: 500, data: {} } },
        {
          message: "auth",
          extensions: { code: ERROR_CODES.AUTHENTICATION_REQUIRED, http_status: 401, data: {} },
        },
      ],
    });

    // WHEN
    handleGraphQLErrors(error, { processErrorMessage });

    // THEN
    expect(processErrorMessage).toHaveBeenCalledWith("boom");
    expect(assignSpy).toHaveBeenCalledOnce();
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
    // GIVEN
    fetchSpy.mockResolvedValueOnce(jsonResponse({ data: { __typename: "Query" } }));

    // WHEN
    await graphqlClient.query({ query: PING });

    // THEN
    const init = fetchSpy.mock.calls[0]?.[1] as RequestInit | undefined;
    expect(init?.method).toBe("POST");
  });

  it("injects __typename into selections (Apollo InMemoryCache parity)", async () => {
    // GIVEN
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

    // THEN
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
    // GIVEN
    fetchSpy
      .mockResolvedValueOnce(jsonResponse(tokenExpiredBody))
      .mockResolvedValueOnce(jsonResponse({ data: { __typename: "Query" } }));
    fetchQuerySpy.mockResolvedValue({ access_token: "new-token", refresh_token: "new-refresh" });

    // WHEN
    const result = await graphqlClient.query({ query: PING });

    // THEN
    expect(result.data).toEqual({ __typename: "Query" });
    expect(result.errors).toBeUndefined();
    expect(fetchQuerySpy).toHaveBeenCalledOnce();
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(assignSpy).not.toHaveBeenCalled();
    const replay = new Headers((fetchSpy.mock.calls[1]?.[1] as RequestInit).headers);
    expect(replay.get(PRIORITY_HEADER)).toBe("high");
  });

  it("bails to /login when TOKEN_EXPIRED persists after the single replay", async () => {
    // GIVEN
    fetchSpy.mockImplementation(() => Promise.resolve(jsonResponse(tokenExpiredBody)));
    fetchQuerySpy.mockResolvedValue({ access_token: "new-token", refresh_token: "new-refresh" });

    // WHEN
    const querying = graphqlClient.query({ query: PING });

    // THEN
    await expect(querying).rejects.toThrow("Token expired");
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(fetchQuerySpy).toHaveBeenCalledOnce();
    expect(assignSpy).toHaveBeenCalled();
  });

  it("rejects a query on GraphQL errors even when the response carries data", async () => {
    // GIVEN
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

    // THEN
    await expect(querying).rejects.toThrow("partial");
  });

  it("rejects when a mutation responds with GraphQL errors", async () => {
    // GIVEN
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

    // THEN
    await expect(mutating).rejects.toThrow("Cannot delete Device 'x'.");
  });
});
