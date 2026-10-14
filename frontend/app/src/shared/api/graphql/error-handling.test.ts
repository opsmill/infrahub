import { CombinedError } from "@urql/core";
import { GraphQLError } from "graphql";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ERROR_CODES } from "@/shared/api/errors";
import { SHED_USER_MESSAGE } from "@/shared/api/rate-limit/shed-envelope";

import { SHED_BODY } from "../../../../tests/fake/shed-response";
import { handleGraphQLErrors, hasOnlyThrownCatalogueCode } from "./error-handling";

function combinedError(errors: Array<Record<string, unknown>>): CombinedError {
  return { graphQLErrors: errors } as unknown as CombinedError;
}

describe("handleGraphQLErrors — a shed request", () => {
  beforeEach(() => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("reports the busy message instead of the server's internal wording", () => {
    // GIVEN
    const processErrorMessage = vi.fn();
    const error = combinedError(SHED_BODY.errors);

    // WHEN
    handleGraphQLErrors(error, { processErrorMessage });

    // THEN
    expect(processErrorMessage).toHaveBeenCalledWith(SHED_USER_MESSAGE);
  });

  it("does not report it as an unregistered catalogue code", () => {
    // GIVEN
    const error = combinedError(SHED_BODY.errors);

    // WHEN
    handleGraphQLErrors(error, { processErrorMessage: vi.fn() });

    // THEN
    expect(console.error).not.toHaveBeenCalled();
  });

  it("still routes a sibling catalogue error", () => {
    // GIVEN
    const processErrorMessage = vi.fn();
    const error = combinedError([
      ...SHED_BODY.errors,
      {
        message: "Node not found",
        extensions: { code: ERROR_CODES.NODE_NOT_FOUND, http_status: 404, data: {} },
      },
    ]);

    // WHEN
    handleGraphQLErrors(error, { processErrorMessage });

    // THEN
    expect(processErrorMessage).toHaveBeenCalledWith(SHED_USER_MESSAGE);
    expect(processErrorMessage).toHaveBeenCalledWith("Node not found");
  });
});

const graphQLError = (extensions: Record<string, unknown>) =>
  new GraphQLError("Request failed", { extensions });

const permissionDenial = () => graphQLError({ code: ERROR_CODES.PERMISSION_DENIED });

const thrownByTransport = (...graphQLErrors: GraphQLError[]) =>
  new Error("Request failed", { cause: new CombinedError({ graphQLErrors }) });

describe("hasOnlyThrownCatalogueCode", () => {
  it("is true when every GraphQL error carries the code", () => {
    const error = thrownByTransport(permissionDenial(), permissionDenial());

    expect(hasOnlyThrownCatalogueCode(error, ERROR_CODES.PERMISSION_DENIED)).toBe(true);
  });

  it("is false when another error comes with it", () => {
    const error = thrownByTransport(permissionDenial(), new GraphQLError("Database unavailable"));

    expect(hasOnlyThrownCatalogueCode(error, ERROR_CODES.PERMISSION_DENIED)).toBe(false);
  });

  it("is false for an error without GraphQL errors", () => {
    expect(hasOnlyThrownCatalogueCode(new Error("offline"), ERROR_CODES.PERMISSION_DENIED)).toBe(
      false
    );
    expect(hasOnlyThrownCatalogueCode("offline", ERROR_CODES.PERMISSION_DENIED)).toBe(false);
  });
});
