import { Observable } from "@apollo/client";
import type { GraphQLFormattedError } from "graphql";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ERROR_CODES } from "@/shared/api/graphql/errors";
import { queryClient } from "@/shared/api/rest/client";

import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from "@/entities/authentication/constants";

import { __navigation, bumpAuthRetryCount, handleGraphQLAuthError } from "./graphqlClientApollo";

describe("bumpAuthRetryCount", () => {
  // Minimal stand-in for Apollo's Operation — only the two methods the
  // helper touches. Keeping it local avoids importing the full Apollo
  // Operation type just for a unit test.
  function makeOperation(initial: Record<string, unknown> = {}) {
    let ctx: Record<string, unknown> = { ...initial };
    return {
      getContext: () => ctx,
      setContext: (patch: Record<string, unknown>) => {
        ctx = { ...ctx, ...patch };
      },
    };
  }

  it("returns 1 and stores the counter on the first call", () => {
    // GIVEN an operation with no prior auth-retry count
    const operation = makeOperation();

    // WHEN we bump
    const count = bumpAuthRetryCount(operation);

    // THEN the helper reports the first attempt and persists it
    expect(count).toBe(1);
    expect(operation.getContext().authRetryCount).toBe(1);
  });

  it("returns 2 on the second call within the same operation", () => {
    // GIVEN an operation that already failed once
    const operation = makeOperation();
    bumpAuthRetryCount(operation);

    // WHEN we bump again (simulates a TOKEN_EXPIRED that came back
    // after the refreshed token was already used to replay once)
    const count = bumpAuthRetryCount(operation);

    // THEN the caller sees >1 and can break the loop
    expect(count).toBe(2);
  });

  it("preserves unrelated context keys", () => {
    // GIVEN an operation carrying caller-set context
    const operation = makeOperation({ branch: "main", processErrorMessage: "fn" });

    // WHEN we bump
    bumpAuthRetryCount(operation);

    // THEN the bump does not erase the existing keys
    expect(operation.getContext().branch).toBe("main");
    expect(operation.getContext().processErrorMessage).toBe("fn");
    expect(operation.getContext().authRetryCount).toBe(1);
  });
});

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

    // AND the operation was tagged so a follow-up TOKEN_EXPIRED bails
    expect(operation.getContext().authRetryCount).toBe(1);

    // AND the replayed operation carries the Bearer-prefixed new token
    const headers = (operation.getContext() as { headers?: { authorization?: string } }).headers;
    expect(headers?.authorization).toBe("Bearer new-token");

    expect(fetchQuerySpy).toHaveBeenCalledOnce();
    expect(forward).toHaveBeenCalledOnce();
  });

  it("second TOKEN_EXPIRED on the same operation bails to /login with ?from=", () => {
    // GIVEN an operation that already burned its single retry
    const operation = makeOperation();
    bumpAuthRetryCount(operation); // simulate prior retry
    const forward = vi.fn();

    // WHEN a second TOKEN_EXPIRED arrives
    const result = handleGraphQLAuthError({
      graphQLErrors: [tokenExpiredError],
      operation,
      forward,
    } as any);

    // THEN the handler bails (returns void, no observable, no replay)
    expect(result).toBeUndefined();
    expect(forward).not.toHaveBeenCalled();

    // AND the user is hard-navigated to /login with the current path encoded
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
