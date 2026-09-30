import { describe, expect, test } from "vitest";

import { getRestErrorMessage } from "@/shared/api/rest/error-message";

describe("getRestErrorMessage", () => {
  test("returns the first message of a REST error body", () => {
    const error = {
      data: null,
      errors: [
        {
          message: "Unable to find the node abc / StorageObject in the database.",
          extensions: { code: 404 },
        },
        { message: "A second error", extensions: { code: 404 } },
      ],
    };

    expect(getRestErrorMessage(error)).toBe(
      "Unable to find the node abc / StorageObject in the database."
    );
  });

  test.each([
    { name: "a plain text body", error: "Internal Server Error" },
    { name: "no body", error: undefined },
    { name: "a body without errors", error: { detail: "Not Found" } },
    { name: "an empty error list", error: { errors: [] } },
    { name: "an error without a message", error: { errors: [{ extensions: { code: 500 } }] } },
    { name: "an empty message", error: { errors: [{ message: "" }] } },
  ])("returns undefined for $name", ({ error }) => {
    expect(getRestErrorMessage(error)).toBeUndefined();
  });
});
