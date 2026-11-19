import { describe, expect, test } from "vitest";

import { ArtifactFileError } from "@/entities/artifacts/domain/model/artifact-file-error";
import { isArtifactContentNotServed } from "@/entities/artifacts/domain/rules/is-artifact-content-not-served";

describe("isArtifactContentNotServed", () => {
  test.each([
    [409, "failed its integrity check"],
    [404, "file not found"],
  ])("is true when the server answered %i", (status, message) => {
    expect(isArtifactContentNotServed(new ArtifactFileError(message, status))).toBe(true);
  });

  test.each([401, 403, 500, 502])("is false when the server answered %i", (status) => {
    expect(isArtifactContentNotServed(new ArtifactFileError("failed", status))).toBe(false);
  });

  test("is false for an error that has no HTTP status", () => {
    expect(isArtifactContentNotServed(new TypeError("Failed to fetch"))).toBe(false);
  });

  test("is false when there is no error", () => {
    expect(isArtifactContentNotServed(null)).toBe(false);
  });
});
