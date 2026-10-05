import { QueryClient, QueryObserver } from "@tanstack/react-query";
import { CombinedError } from "@urql/core";
import { GraphQLError } from "graphql";
import { afterEach, describe, expect, it, vi } from "vitest";

import { pollWhileHealthy, retryBackgroundQuery } from "@/shared/api/background-query";
import { ERROR_CODES } from "@/shared/api/errors";
import { HTTP_TOO_MANY_REQUESTS } from "@/shared/api/rate-limit/shed-envelope";

const thrownWith = (extensions: Record<string, unknown>) =>
  new Error("Request failed", {
    cause: new CombinedError({
      graphQLErrors: [new GraphQLError("Request failed", { extensions })],
    }),
  });

const permissionDenied = () => thrownWith({ code: ERROR_CODES.PERMISSION_DENIED });

describe("retryBackgroundQuery", () => {
  it("retries any other failure twice", () => {
    const error = new Error("Network error");

    expect(retryBackgroundQuery(0, error)).toBe(true);
    expect(retryBackgroundQuery(1, error)).toBe(true);
    expect(retryBackgroundQuery(2, error)).toBe(false);
  });

  it("doesn't retry a permission denial", () => {
    expect(retryBackgroundQuery(0, permissionDenied())).toBe(false);
  });

  it("doesn't retry a request the transport already retried after the server shed it", () => {
    expect(retryBackgroundQuery(0, thrownWith({ code: HTTP_TOO_MANY_REQUESTS }))).toBe(false);
  });
});

describe("pollWhileHealthy", () => {
  it("polls while active and the last fetch succeeded", () => {
    expect(pollWhileHealthy(true, 10_000, { state: { status: "success" } } as never)).toBe(10_000);
    expect(pollWhileHealthy(false, 10_000, { state: { status: "success" } } as never)).toBe(false);
  });

  it("stops polling once a fetch has failed", () => {
    expect(pollWhileHealthy(true, 10_000, { state: { status: "error" } } as never)).toBe(false);
  });
});

describe("a polled background query", () => {
  const queryClient = new QueryClient();

  afterEach(() => {
    queryClient.clear();
  });

  it("sends a denied request once and doesn't poll it again", async () => {
    // GIVEN
    const queryFn = vi.fn().mockRejectedValue(permissionDenied());
    const observer = new QueryObserver(queryClient, {
      queryKey: ["background", "denied"],
      queryFn,
      retry: retryBackgroundQuery,
      refetchInterval: (query) => pollWhileHealthy(true, 20, query),
    });

    // WHEN
    const unsubscribe = observer.subscribe(() => {});
    await expect.poll(() => observer.getCurrentResult().status).toBe("error");
    await new Promise((resolve) => setTimeout(resolve, 150));
    unsubscribe();

    // THEN
    expect(queryFn).toHaveBeenCalledTimes(1);
  });
});
