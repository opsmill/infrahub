import { describe, expect, it } from "vitest";

import {
  type CatalogueError,
  ERROR_CODES,
  type ErrorCode,
  isCatalogueError,
  parseCatalogueError,
} from "./index";

describe("parseCatalogueError", () => {
  it("narrows NODE_NOT_FOUND with its typed data", () => {
    // GIVEN
    const extensions = {
      code: "NODE_NOT_FOUND",
      http_status: 404,
      data: { node_kind: "CoreAccount", identifier: "abc-123" },
    };

    // WHEN
    const parsed = parseCatalogueError(extensions);

    // THEN
    expect(parsed).toEqual({
      code: ERROR_CODES.NODE_NOT_FOUND,
      http_status: 404,
      data: { node_kind: "CoreAccount", identifier: "abc-123" },
    });
  });

  it("narrows AUTHENTICATION_REQUIRED with empty data", () => {
    // GIVEN
    const extensions = { code: "AUTHENTICATION_REQUIRED", http_status: 401, data: {} };

    // WHEN
    const parsed = parseCatalogueError(extensions);

    // THEN
    expect(parsed.code).toBe(ERROR_CODES.AUTHENTICATION_REQUIRED);
    expect(parsed.http_status).toBe(401);
    expect(parsed.data).toEqual({});
  });

  it("narrows TOKEN_EXPIRED and preserves expired_at", () => {
    // GIVEN
    const extensions = {
      code: "TOKEN_EXPIRED",
      http_status: 401,
      data: { expired_at: "2026-05-27T10:00:00Z" },
    };

    // WHEN
    const parsed = parseCatalogueError(extensions);

    // THEN
    expect(parsed).toEqual({
      code: ERROR_CODES.TOKEN_EXPIRED,
      http_status: 401,
      data: { expired_at: "2026-05-27T10:00:00Z" },
    });
  });

  it("narrows PERMISSION_DENIED with nullable action/resource_kind", () => {
    // GIVEN
    const extensions = {
      code: "PERMISSION_DENIED",
      http_status: 403,
      data: { action: "update", resource_kind: "CoreAccount" },
    };

    // WHEN
    const parsed = parseCatalogueError(extensions);

    // THEN
    expect(parsed.code).toBe(ERROR_CODES.PERMISSION_DENIED);
    expect(parsed.data).toEqual({ action: "update", resource_kind: "CoreAccount" });
  });

  it.each([
    ["ATTRIBUTE_REQUIRED", { node_kind: "CoreAccount", field_name: "name" }, 422],
    [
      "ATTRIBUTE_INVALID_TYPE",
      {
        node_kind: "CoreAccount",
        field_name: "name",
        expected_type: "String",
        received_type: "Number",
      },
      422,
    ],
    [
      "ATTRIBUTE_CONSTRAINT_VIOLATION",
      {
        node_kind: "CoreAccount",
        field_name: "name",
        constraint: "regex",
        detail: "must match ^[a-z]+$",
      },
      422,
    ],
    ["BRANCH_NOT_FOUND", { branch_name: "feature-x" }, 400],
    ["SCHEMA_NOT_FOUND", { kind: "CoreAccount" }, 422],
  ])("narrows %s passing through http_status and data", (code, data, httpStatus) => {
    // GIVEN
    const extensions = { code, http_status: httpStatus, data };

    // WHEN
    const parsed = parseCatalogueError(extensions);

    // THEN
    expect(parsed.code).toBe(code);
    expect(parsed.http_status).toBe(httpStatus);
    expect(parsed.data).toEqual(data);
  });

  it("returns UNDEFINED_ERROR for an unknown code", () => {
    // GIVEN
    const extensions = { code: "SOMETHING_NEW", http_status: 500, data: {} };

    // WHEN
    const parsed = parseCatalogueError(extensions);

    // THEN
    expect(parsed).toEqual({
      code: ERROR_CODES.UNDEFINED_ERROR,
      http_status: 500,
      data: {},
    });
  });

  it.each([
    ["null", null],
    ["undefined", undefined],
    ["a string", "AUTHENTICATION_REQUIRED"],
    ["a number", 401],
    ["a boolean", true],
  ])("returns UNDEFINED_ERROR when extensions is %s", (_label, input) => {
    // WHEN
    const parsed = parseCatalogueError(input);

    // THEN
    expect(parsed).toEqual({
      code: ERROR_CODES.UNDEFINED_ERROR,
      http_status: 500,
      data: {},
    });
  });

  it("returns UNDEFINED_ERROR when code is missing", () => {
    // GIVEN
    const extensions = { http_status: 401, data: {} };

    // WHEN
    const parsed = parseCatalogueError(extensions);

    // THEN
    expect(parsed.code).toBe(ERROR_CODES.UNDEFINED_ERROR);
  });

  it("defaults http_status to the catalogue value when missing or non-numeric", () => {
    // GIVEN — AUTHENTICATION_REQUIRED's catalogue http_status is 401
    const missing = parseCatalogueError({ code: "AUTHENTICATION_REQUIRED", data: {} });
    const garbage = parseCatalogueError({
      code: "AUTHENTICATION_REQUIRED",
      http_status: "not-a-number",
      data: {},
    });

    // THEN — fall back to the catalogue's known http_status, not 500
    expect(missing.http_status).toBe(401);
    expect(garbage.http_status).toBe(401);
  });

  it("defaults data to {} when missing or non-object", () => {
    // GIVEN
    const missing = parseCatalogueError({
      code: "AUTHENTICATION_REQUIRED",
      http_status: 401,
    });
    const garbage = parseCatalogueError({
      code: "AUTHENTICATION_REQUIRED",
      http_status: 401,
      data: "not-an-object",
    });

    // THEN
    expect(missing.data).toEqual({});
    expect(garbage.data).toEqual({});
  });
});

describe("isCatalogueError", () => {
  it("accepts a known code with arbitrary payload", () => {
    expect(isCatalogueError({ code: "NODE_NOT_FOUND", http_status: 404, data: {} })).toBe(true);
  });

  it("rejects an unknown code", () => {
    expect(isCatalogueError({ code: "TOTALLY_FAKE", http_status: 500, data: {} })).toBe(false);
  });

  it.each([
    ["null", null],
    ["undefined", undefined],
    ["a string", "NODE_NOT_FOUND"],
    ["a number", 42],
    ["an empty object", {}],
    ["an object with non-string code", { code: 42 }],
  ])("rejects %s", (_label, input) => {
    expect(isCatalogueError(input)).toBe(false);
  });
});

/**
 * Compile-time exhaustiveness guard. If a new code is added to ERROR_CODES
 * without a corresponding case here, the `unhandled: never` assignment fails
 * to compile because the residual `code` won't narrow to `never`. This is a
 * type-level check that runs at `tsc`, not at vitest.
 */
describe("ErrorCode exhaustiveness", () => {
  it("forces every ErrorCode to have a switch arm in this file", () => {
    const assertExhaustive = (code: ErrorCode): string => {
      switch (code) {
        case ERROR_CODES.NODE_NOT_FOUND:
        case ERROR_CODES.AUTHENTICATION_REQUIRED:
        case ERROR_CODES.TOKEN_EXPIRED:
        case ERROR_CODES.PERMISSION_DENIED:
        case ERROR_CODES.ATTRIBUTE_REQUIRED:
        case ERROR_CODES.ATTRIBUTE_INVALID_TYPE:
        case ERROR_CODES.ATTRIBUTE_CONSTRAINT_VIOLATION:
        case ERROR_CODES.BRANCH_NOT_FOUND:
        case ERROR_CODES.SCHEMA_NOT_FOUND:
        case ERROR_CODES.UNDEFINED_ERROR:
          return code;
        default: {
          const unhandled: never = code;
          return unhandled;
        }
      }
    };

    expect(assertExhaustive(ERROR_CODES.NODE_NOT_FOUND)).toBe("NODE_NOT_FOUND");
  });

  it("locks the CatalogueError union to ErrorCode values", () => {
    // Compile-time check: any CatalogueError.code must be an ErrorCode.
    const variant: CatalogueError = {
      code: ERROR_CODES.UNDEFINED_ERROR,
      http_status: 500,
      data: {} as never,
    };
    const code: ErrorCode = variant.code;
    expect(code).toBe(ERROR_CODES.UNDEFINED_ERROR);
  });
});
