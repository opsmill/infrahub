import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { PRIORITY_HEADER } from "@/shared/api/priority";

import { redirectToLogin } from "@/entities/authentication/domain/use-cases/redirect-to-login";
import { refreshAccessToken } from "@/entities/authentication/domain/use-cases/refresh-access-token";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";

import { generateBranch } from "../../../../tests/fake/branch";
import { sandboxFetch, useGraphiqlTransport } from "./use-graphiql-transport";

vi.mock("@/entities/authentication/domain/use-cases/redirect-to-login");
vi.mock("@/entities/authentication/domain/use-cases/refresh-access-token");
vi.mock("@/entities/branches/ui/branches-provider");

const GRAPHQL_URL = "http://localhost:8000/graphql/main";
const SESSION_TOKEN = "session-token";
const REFRESHED_TOKEN = "refreshed-token";

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const tokenExpiredResponse = () =>
  jsonResponse(
    {
      data: null,
      errors: [
        {
          message: "Expired Signature",
          extensions: { code: "TOKEN_EXPIRED", http_status: 401, data: { expired_at: null } },
        },
      ],
    },
    401
  );

describe("GraphiQL sandbox fetch", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  const send = (headers?: Record<string, string>) =>
    sandboxFetch(GRAPHQL_URL, {
      method: "POST",
      body: JSON.stringify({ query: "{ __typename }" }),
      headers,
    });

  const sentHeaders = (call = 0) =>
    new Headers(fetchSpy.mock.calls[call]?.[1]?.headers as HeadersInit);

  beforeEach(() => {
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => (key === "access_token" ? SESSION_TOKEN : null),
      setItem: () => {},
      removeItem: () => {},
      clear: () => {},
    });

    fetchSpy = vi.fn(async () => jsonResponse({ data: null }));
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetAllMocks();
  });

  describe("outbound headers", () => {
    it("sends the session token at high priority", async () => {
      // WHEN
      await send();

      // THEN
      expect(fetchSpy).toHaveBeenCalledOnce();
      expect(sentHeaders().get(PRIORITY_HEADER)).toBe("high");
      expect(sentHeaders().get("authorization")).toBe(`Bearer ${SESSION_TOKEN}`);
    });

    it("lets headers from the Headers tab replace the session token", async () => {
      // WHEN
      await send({ Authorization: "Bearer api-token", "X-Custom": "value" });

      // THEN
      expect(sentHeaders().get("authorization")).toBe("Bearer api-token");
      expect(sentHeaders().get("x-custom")).toBe("value");
    });
  });

  describe("rejected session token", () => {
    it("runs the query with a refreshed token without reloading the page", async () => {
      // GIVEN
      fetchSpy
        .mockResolvedValueOnce(tokenExpiredResponse())
        .mockResolvedValueOnce(jsonResponse({ data: { __typename: "Query" } }));
      vi.mocked(refreshAccessToken).mockResolvedValue({ access_token: REFRESHED_TOKEN });

      // WHEN
      const response = await send();

      // THEN
      expect(refreshAccessToken).toHaveBeenCalledOnce();
      expect(fetchSpy).toHaveBeenCalledTimes(2);
      expect(sentHeaders(1).get("authorization")).toBe(`Bearer ${REFRESHED_TOKEN}`);
      expect(response.status).toBe(200);
      expect(await response.json()).toEqual({ data: { __typename: "Query" } });
      expect(redirectToLogin).not.toHaveBeenCalled();
    });

    it("sends the user to the login page when the session cannot be refreshed", async () => {
      // GIVEN
      fetchSpy.mockResolvedValueOnce(tokenExpiredResponse());
      vi.mocked(refreshAccessToken).mockRejectedValue(new Error("Refresh token expired"));

      // WHEN
      const response = await send();

      // THEN
      expect(redirectToLogin).toHaveBeenCalledOnce();
      expect(fetchSpy).toHaveBeenCalledOnce();
      expect(response.status).toBe(401);
    });

    it("keeps the user on the page when the query fails after a successful refresh", async () => {
      // GIVEN
      const networkError = new TypeError("Failed to fetch");
      fetchSpy.mockResolvedValueOnce(tokenExpiredResponse()).mockRejectedValueOnce(networkError);
      vi.mocked(refreshAccessToken).mockResolvedValue({ access_token: REFRESHED_TOKEN });

      // WHEN
      const response = send();

      // THEN
      await expect(response).rejects.toBe(networkError);
      expect(redirectToLogin).not.toHaveBeenCalled();
    });

    it("never refreshes a token typed in the Headers tab", async () => {
      // GIVEN
      fetchSpy.mockResolvedValueOnce(tokenExpiredResponse());

      // WHEN
      const response = await send({ Authorization: "Bearer expired-api-token" });

      // THEN
      expect(refreshAccessToken).not.toHaveBeenCalled();
      expect(redirectToLogin).not.toHaveBeenCalled();
      expect(response.status).toBe(401);
    });

    it("refreshes a session token the server rejects as invalid", async () => {
      // GIVEN
      fetchSpy
        .mockResolvedValueOnce(
          jsonResponse(
            {
              errors: [
                { message: "Invalid token", extensions: { code: "AUTHENTICATION_REQUIRED" } },
              ],
            },
            401
          )
        )
        .mockResolvedValueOnce(jsonResponse({ data: { __typename: "Query" } }));
      vi.mocked(refreshAccessToken).mockResolvedValue({ access_token: REFRESHED_TOKEN });

      // WHEN
      const response = await send();

      // THEN
      expect(refreshAccessToken).toHaveBeenCalledOnce();
      expect(sentHeaders(1).get("authorization")).toBe(`Bearer ${REFRESHED_TOKEN}`);
      expect(response.status).toBe(200);
    });

    it("never refreshes without a session", async () => {
      // GIVEN
      vi.stubGlobal("localStorage", {
        getItem: () => null,
        setItem: () => {},
        removeItem: () => {},
        clear: () => {},
      });
      fetchSpy.mockResolvedValueOnce(tokenExpiredResponse());

      // WHEN
      const response = await send();

      // THEN
      expect(sentHeaders().get("authorization")).toBeNull();
      expect(refreshAccessToken).not.toHaveBeenCalled();
      expect(redirectToLogin).not.toHaveBeenCalled();
      expect(response.status).toBe(401);
    });
  });
});

describe("GraphiQL sandbox transport", () => {
  it("hands a subscription to GraphiQL as a stream", async () => {
    // GIVEN
    vi.mocked(useCurrentBranch).mockReturnValue({
      currentBranch: generateBranch({ name: "main" }),
      setCurrentBranch: () => {},
    });
    const { result } = await renderHook(() => useGraphiqlTransport());

    // WHEN
    const sent = result.current.send({ query: "subscription { __typename }" });

    // THEN
    expect(Symbol.asyncIterator in sent).toBe(true);
  });
});
