import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PRIORITY_HEADER } from "@/shared/api/priority";

import { createBaseFetcher } from "./use-graphiql-fetcher";

describe("GraphiQL base fetcher — outbound X-Priority header", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.stubGlobal("localStorage", {
      getItem: () => null,
      setItem: () => {},
      removeItem: () => {},
      clear: () => {},
    });

    fetchSpy = vi.fn(
      async () =>
        new Response(JSON.stringify({ data: null }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
    );
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("stamps X-Priority: high on the sandbox fetch", async () => {
    const fetcher = createBaseFetcher("http://localhost:8000/graphql/main");

    await fetcher({ query: "{ __typename }" } as never);

    expect(fetchSpy).toHaveBeenCalledOnce();
    const headers = fetchSpy.mock.calls[0]?.[1]?.headers as Record<string, string>;
    expect(headers[PRIORITY_HEADER]).toBe("high");
  });
});
