import { describe, expect, it } from "vitest";

import { isShedErrorItem, isShedResponse } from "./shed-envelope";

// The envelope the API answers a shed request with.
const SHED_BODY = {
  data: null,
  errors: [{ message: "Server is shedding load; retry later.", extensions: { code: 429 } }],
};

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("isShedErrorItem", () => {
  it("recognises the integer HTTP status the shed envelope carries", () => {
    expect(isShedErrorItem({ code: 429 })).toBe(true);
  });

  it("rejects a catalogue error, whose code is a string identifier", () => {
    expect(isShedErrorItem({ code: "TOKEN_EXPIRED", http_status: 401 })).toBe(false);
  });

  it("rejects the status as a string, which no Infrahub surface sends", () => {
    expect(isShedErrorItem({ code: "429" })).toBe(false);
  });

  it.each([null, undefined, "429", 429])("rejects the non-object %o", (extensions) => {
    expect(isShedErrorItem(extensions)).toBe(false);
  });
});

describe("isShedResponse", () => {
  it("recognises a 429 carrying the shed envelope", async () => {
    await expect(isShedResponse(jsonResponse(SHED_BODY, 429))).resolves.toBe(true);
  });

  it("leaves the body readable for the caller", async () => {
    const response = jsonResponse(SHED_BODY, 429);

    await isShedResponse(response);

    await expect(response.json()).resolves.toEqual(SHED_BODY);
  });

  it("rejects a 429 from something else in front of the API", async () => {
    await expect(isShedResponse(jsonResponse({ detail: "slow down" }, 429))).resolves.toBe(false);
  });

  it("rejects a 429 whose body is not JSON", async () => {
    const response = new Response("<html>Too Many Requests</html>", { status: 429 });

    await expect(isShedResponse(response)).resolves.toBe(false);
  });

  it("rejects the envelope on any other status", async () => {
    await expect(isShedResponse(jsonResponse(SHED_BODY, 200))).resolves.toBe(false);
  });
});
