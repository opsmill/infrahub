import { describe, expect, it } from "vitest";

import {
  foreignRateLimitResponse,
  jsonResponse,
  SHED_BODY,
  shedResponse,
} from "../../../../tests/fake/shed-response";
import {
  isShedErrorItem,
  isShedResponse,
  SHED_MARKER_HEADER,
  SHED_MARKER_VALUE,
  SHED_USER_MESSAGE,
  withShedWording,
} from "./shed-envelope";

describe("isShedErrorItem", () => {
  it("recognizes the integer HTTP status the shed envelope has", () => {
    // GIVEN
    const extensions = { code: 429 };

    // WHEN
    const isShed = isShedErrorItem(extensions);

    // THEN
    expect(isShed).toBe(true);
  });

  it("rejects a catalogue error, whose code is a string identifier", () => {
    // GIVEN
    const extensions = { code: "TOKEN_EXPIRED", http_status: 401 };

    // WHEN
    const isShed = isShedErrorItem(extensions);

    // THEN
    expect(isShed).toBe(false);
  });

  it("rejects the status as a string, which no Infrahub surface sends", () => {
    // GIVEN
    const extensions = { code: "429" };

    // WHEN
    const isShed = isShedErrorItem(extensions);

    // THEN
    expect(isShed).toBe(false);
  });

  it.each([null, undefined, "429", 429])("rejects the non-object %o", (extensions) => {
    // GIVEN
    const notAnObject = extensions;

    // WHEN
    const isShed = isShedErrorItem(notAnObject);

    // THEN
    expect(isShed).toBe(false);
  });
});

describe("isShedResponse", () => {
  it("recognizes a 429 marked by the admission layer", () => {
    // GIVEN
    const response = shedResponse();

    // WHEN
    const isShed = isShedResponse(response);

    // THEN
    expect(isShed).toBe(true);
  });

  it("rejects a 429 whose body is the shed envelope but that lacks the marker", () => {
    // GIVEN a body a handler's error could have produced
    const response = jsonResponse(SHED_BODY, 429);

    // WHEN
    const isShed = isShedResponse(response);

    // THEN
    expect(isShed).toBe(false);
  });

  it("rejects a 429 from something else in front of the API", () => {
    // GIVEN
    const response = foreignRateLimitResponse();

    // WHEN
    const isShed = isShedResponse(response);

    // THEN
    expect(isShed).toBe(false);
  });

  it("rejects the marker on any other status", () => {
    // GIVEN
    const response = jsonResponse(SHED_BODY, 200, { [SHED_MARKER_HEADER]: SHED_MARKER_VALUE });

    // WHEN
    const isShed = isShedResponse(response);

    // THEN
    expect(isShed).toBe(false);
  });

  it("leaves the body untouched for the caller", async () => {
    // GIVEN
    const response = shedResponse();

    // WHEN
    isShedResponse(response);

    // THEN
    expect(response.bodyUsed).toBe(false);
    await expect(response.json()).resolves.toEqual(SHED_BODY);
  });
});

describe("withShedWording", () => {
  it("replaces the server's wording on a shed envelope with the user-facing one", async () => {
    // GIVEN
    const response = shedResponse();

    // WHEN
    const reworded = await withShedWording(response);

    // THEN
    await expect(reworded.json()).resolves.toEqual({
      ...SHED_BODY,
      errors: [{ ...SHED_BODY.errors[0], message: SHED_USER_MESSAGE }],
    });
  });

  it("keeps the shed's status and headers on the copy", async () => {
    // GIVEN
    const response = shedResponse({ "Retry-After": "3" });

    // WHEN
    const reworded = await withShedWording(response);

    // THEN
    expect(reworded.status).toBe(429);
    expect(reworded.headers.get("Retry-After")).toBe("3");
    expect(reworded.headers.get(SHED_MARKER_HEADER)).toBe(SHED_MARKER_VALUE);
  });

  it("leaves a 429 from something else in front of the API untouched", async () => {
    // GIVEN
    const response = foreignRateLimitResponse();

    // WHEN
    const result = await withShedWording(response);

    // THEN
    expect(result).toBe(response);
    await expect(result.json()).resolves.toEqual({ detail: "slow down" });
  });

  it("leaves any other response untouched", async () => {
    // GIVEN
    const response = jsonResponse({ data: { ok: true } }, 200);

    // WHEN
    const result = await withShedWording(response);

    // THEN
    expect(result).toBe(response);
  });
});
