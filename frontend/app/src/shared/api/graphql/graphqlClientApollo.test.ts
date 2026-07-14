import { ApolloLink, execute, gql, Observable } from "@apollo/client";
import type { GraphQLFormattedError } from "graphql";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ERROR_CODES } from "@/shared/api/errors";
import { PRIORITY_HEADER } from "@/shared/api/priority";
import { queryClient } from "@/shared/api/rest/client";

import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from "@/entities/authentication/api/token-storage";
import { __navigation } from "@/entities/authentication/domain/use-cases/redirect-to-login";

import { handleGraphQLAuthError, priorityLink } from "./graphqlClientApollo";

describe("handleGraphQLAuthError — TOKEN_EXPIRED retry-then-bail loop", () => {
  // Minimal stand-in for Apollo's `Operation`. The handler only touches
  // `getContext`/`setContext`, so we don't bring in the full Apollo type
  // just to satisfy a structural shape.
  function makeOperation() {
    let ctx: Record<string, unknown> = {};
    return {
      getContext: () => ctx,
      setContext: (patch: Record<string, unknown>) => {
        ctx = { ...ctx, ...patch };
      },
    };
  }

  const tokenExpiredError = {
    message: "Token expired",
    extensions: { code: ERROR_CODES.TOKEN_EXPIRED, http_status: 401, data: {} },
  } satisfies Partial<GraphQLFormattedError> as GraphQLFormattedError;

  let assignSpy: ReturnType<typeof vi.fn>;
  let fetchQuerySpy: ReturnType<typeof vi.spyOn>;
  let originalAssign: typeof __navigation.assign;

  beforeEach(() => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "old-token");
    localStorage.setItem(REFRESH_TOKEN_KEY, "old-refresh");

    // Swap the navigation holder's `assign` so the handler's hard-nav lands
    // on a spy rather than actually navigating the test page. Restored in
    // afterEach so unrelated tests don't see the stub.
    originalAssign = __navigation.assign;
    assignSpy = vi.fn();
    __navigation.assign = assignSpy as unknown as typeof __navigation.assign;

    fetchQuerySpy = vi.spyOn(queryClient, "fetchQuery");
  });

  afterEach(() => {
    __navigation.assign = originalAssign;
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("first TOKEN_EXPIRED refreshes the token and replays with Bearer header", async () => {
    // GIVEN a refresh that returns a fresh access token
    fetchQuerySpy.mockResolvedValue({ access_token: "new-token", refresh_token: "new-refresh" });
    const operation = makeOperation();
    // Stand-in for Apollo's `forward` — emits a single empty result so the
    // retry observable completes cleanly.
    const forward = vi.fn(() => Observable.of({ data: null }));

    // WHEN the handler sees a TOKEN_EXPIRED for the first time on this op
    const result = handleGraphQLAuthError({
      graphQLErrors: [tokenExpiredError],
      operation,
      forward,
    } as any);

    // THEN it returns the retry observable
    expect(result).toBeInstanceOf(Observable);

    // Drive the observable through to completion so the refresh promise
    // and forward subscription get a chance to run.
    await new Promise<void>((resolve, reject) => {
      (result as Observable<unknown>).subscribe({
        complete: () => resolve(),
        error: (err) => reject(err),
      });
    });

    // AND the replayed operation carries the Bearer-prefixed new token
    const headers = (operation.getContext() as { headers?: { authorization?: string } }).headers;
    expect(headers?.authorization).toBe("Bearer new-token");

    expect(fetchQuerySpy).toHaveBeenCalledOnce();
    expect(forward).toHaveBeenCalledOnce();
    // AND the user is NOT bounced — the happy path completes cleanly
    expect(assignSpy).not.toHaveBeenCalled();
  });

  it("replayed result that still carries TOKEN_EXPIRED bails to /login", async () => {
    // GIVEN a refresh that succeeds, but the replayed request still
    // comes back with TOKEN_EXPIRED (clock skew, malformed refreshed
    // token, server-side revoke between refresh and replay). Apollo's
    // onError does NOT re-invoke our handler for this result, so the
    // bail has to be detected inside `retryWithRefreshedToken` itself.
    fetchQuerySpy.mockResolvedValue({ access_token: "new-token", refresh_token: "new-refresh" });
    const operation = makeOperation();
    const replayedResult = { errors: [tokenExpiredError] };
    const forward = vi.fn(() => Observable.of(replayedResult));

    // WHEN the handler runs the retry path
    const result = handleGraphQLAuthError({
      graphQLErrors: [tokenExpiredError],
      operation,
      forward,
    } as any);

    // THEN the retry observable errors out with the persistence sentinel
    await expect(
      new Promise<void>((resolve, reject) => {
        (result as Observable<unknown>).subscribe({
          next: () => {},
          complete: () => resolve(),
          error: (err) => reject(err),
        });
      })
    ).rejects.toThrow(/persisted/i);

    // AND the user is hard-navigated to /login with `?from=…`
    expect(assignSpy).toHaveBeenCalledOnce();
    const target = assignSpy.mock.calls[0]?.[0] as string | undefined;
    expect(target).toMatch(/^\/login\?from=/);

    // AND the stale credentials were cleared so the next mount won't loop
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull();
  });

  it("refresh failure clears tokens and bounces to /login", async () => {
    // GIVEN a refresh that rejects (refresh token expired / server revoked)
    fetchQuerySpy.mockRejectedValue(new Error("refresh failed"));
    const operation = makeOperation();
    const forward = vi.fn();

    // WHEN the handler runs the retry path
    const result = handleGraphQLAuthError({
      graphQLErrors: [tokenExpiredError],
      operation,
      forward,
    } as any);

    // THEN the retry observable errors out
    await expect(
      new Promise<void>((resolve, reject) => {
        (result as Observable<unknown>).subscribe({
          complete: () => resolve(),
          error: (err) => reject(err),
        });
      })
    ).rejects.toThrow("refresh failed");

    // AND the user is bounced to /login instead of being left signed-in
    // against a session the server has already disowned.
    expect(assignSpy).toHaveBeenCalledOnce();
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
    expect(forward).not.toHaveBeenCalled();
  });
});

describe("priorityLink — outbound X-Priority header", () => {
  // Observe the header at the transport boundary: a terminating link records
  // the context headers the priority link produced, mirroring the existing
  // Observable.of forward pattern above.
  function runThroughPriorityLink(context?: Record<string, unknown>) {
    let captured: Record<string, unknown> | undefined;

    const captureLink = new ApolloLink((operation) => {
      captured = operation.getContext().headers as Record<string, unknown>;
      return Observable.of({ data: null });
    });

    const link = ApolloLink.from([priorityLink, captureLink]);

    return new Promise<Record<string, unknown> | undefined>((resolve, reject) => {
      execute(link, { query: gql`{ __typename }`, context }).subscribe({
        complete: () => resolve(captured),
        error: (err) => reject(err),
      });
    });
  }

  it("stamps X-Priority: high when the operation has no context.priority", async () => {
    const headers = await runThroughPriorityLink();
    expect(headers?.[PRIORITY_HEADER]).toBe("high");
  });

  it("stamps X-Priority: low when the operation declares context.priority = low", async () => {
    const headers = await runThroughPriorityLink({ priority: "low" });
    expect(headers?.[PRIORITY_HEADER]).toBe("low");
  });
});

describe("retryWithRefreshedToken (via handleGraphQLAuthError) — X-Priority survives 401 replay", () => {
  // Node-mode: exercise the REAL exported handler. The happy replay path never
  // reaches redirectToLogin, but getAccessToken/token clearing read
  // localStorage, so provide a minimal in-memory stub (no token needed here —
  // the refresh is driven through the fetchQuery spy).
  const tokenExpiredError = {
    message: "Token expired",
    extensions: { code: ERROR_CODES.TOKEN_EXPIRED, http_status: 401, data: {} },
  } satisfies Partial<GraphQLFormattedError> as GraphQLFormattedError;

  let fetchQuerySpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.stubGlobal("localStorage", {
      getItem: () => null,
      setItem: () => {},
      removeItem: () => {},
      clear: () => {},
    });
    fetchQuerySpy = vi.spyOn(queryClient, "fetchQuery");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  // Operation whose context already carries the X-Priority the priorityLink
  // stamped on the first pass, alongside the now-expired auth header — exactly
  // the state `retryWithRefreshedToken` reads via `operation.getContext()`.
  function makeOperationWithPriority() {
    let ctx: Record<string, unknown> = {
      headers: { [PRIORITY_HEADER]: "high", authorization: "Bearer old-token" },
    };
    return {
      getContext: () => ctx,
      setContext: (patch: Record<string, unknown>) => {
        ctx = { ...ctx, ...patch };
      },
    };
  }

  it("re-carries the original X-Priority after the refresh+replay (relies on the ...oldHeaders spread)", async () => {
    // GIVEN a refresh that returns a fresh token
    fetchQuerySpy.mockResolvedValue({ access_token: "new-token", refresh_token: "new-refresh" });
    const operation = makeOperationWithPriority();
    const forward = vi.fn(() => Observable.of({ data: null }));

    // WHEN the real handler runs the TOKEN_EXPIRED retry path
    const result = handleGraphQLAuthError({
      graphQLErrors: [tokenExpiredError],
      operation,
      forward,
    } as any);

    await new Promise<void>((resolve, reject) => {
      (result as Observable<unknown>).subscribe({
        complete: () => resolve(),
        error: (err) => reject(err),
      });
    });

    // THEN the replayed operation's context still carries X-Priority (preserved
    // by `{ ...oldHeaders, authorization }`) alongside the refreshed Bearer.
    const headers = (operation.getContext() as { headers?: Record<string, string> }).headers;
    expect(headers?.[PRIORITY_HEADER]).toBe("high");
    expect(headers?.authorization).toBe("Bearer new-token");
    expect(forward).toHaveBeenCalledOnce();
  });
});
