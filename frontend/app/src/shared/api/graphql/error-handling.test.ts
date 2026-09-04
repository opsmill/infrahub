import type { CombinedError } from "@urql/core";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ERROR_CODES } from "@/shared/api/errors";
import { SHED_USER_MESSAGE } from "@/shared/api/rate-limit/shed-envelope";

import { handleGraphQLErrors } from "./error-handling";

function combinedError(errors: Array<Record<string, unknown>>): CombinedError {
  return { graphQLErrors: errors } as unknown as CombinedError;
}

describe("handleGraphQLErrors — a shed request", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("reports the busy message instead of the server's internal wording", () => {
    const processErrorMessage = vi.fn();
    vi.spyOn(console, "warn").mockImplementation(() => {});

    handleGraphQLErrors(
      combinedError([
        { message: "Server is shedding load; retry later.", extensions: { code: 429 } },
      ]),
      { processErrorMessage }
    );

    expect(processErrorMessage).toHaveBeenCalledWith(SHED_USER_MESSAGE);
  });

  it("does not report it as an unregistered catalogue code", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    vi.spyOn(console, "warn").mockImplementation(() => {});

    handleGraphQLErrors(combinedError([{ message: "shed", extensions: { code: 429 } }]), {
      processErrorMessage: vi.fn(),
    });

    expect(consoleError).not.toHaveBeenCalled();
  });

  it("still routes a sibling catalogue error", () => {
    const processErrorMessage = vi.fn();
    vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.spyOn(console, "error").mockImplementation(() => {});

    handleGraphQLErrors(
      combinedError([
        { message: "shed", extensions: { code: 429 } },
        {
          message: "Node not found",
          extensions: { code: ERROR_CODES.NODE_NOT_FOUND, http_status: 404, data: {} },
        },
      ]),
      { processErrorMessage }
    );

    expect(processErrorMessage).toHaveBeenCalledWith(SHED_USER_MESSAGE);
    expect(processErrorMessage).toHaveBeenCalledWith("Node not found");
  });
});
