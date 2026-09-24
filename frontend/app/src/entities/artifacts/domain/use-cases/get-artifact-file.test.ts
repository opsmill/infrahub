import { beforeEach, describe, expect, test, vi } from "vitest";

import { getArtifactFileFromApi } from "@/entities/artifacts/api/get-artifact-file-from-api";
import { getArtifactFile } from "@/entities/artifacts/domain/use-cases/get-artifact-file";

vi.mock("@/entities/artifacts/api/get-artifact-file-from-api");

type FileResult = Awaited<ReturnType<typeof getArtifactFileFromApi>>;

function mockResponse(result: { data?: unknown; error?: unknown }) {
  vi.mocked(getArtifactFileFromApi).mockResolvedValue(result as unknown as FileResult);
}

describe("getArtifactFile", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("returns the text content of the artifact", async () => {
    mockResponse({ data: "hostname leaf01\n" });

    await expect(getArtifactFile({ storageId: "abc" })).resolves.toBe("hostname leaf01\n");
  });

  test("surfaces the message the API returned when it refuses the artifact", async () => {
    mockResponse({
      error: {
        data: null,
        errors: [
          {
            message:
              "The artifact stored as abc does not match the checksum recorded for it: it was modified or corrupted outside of Infrahub and is not served.",
            extensions: { code: 409 },
          },
        ],
      },
    });

    await expect(getArtifactFile({ storageId: "abc" })).rejects.toThrow(
      "The artifact stored as abc does not match the checksum recorded for it: it was modified or corrupted outside of Infrahub and is not served."
    );
  });

  test("surfaces the API message for a binary artifact too", async () => {
    mockResponse({
      error: { errors: [{ message: "Unable to find the node", extensions: { code: 404 } }] },
    });

    await expect(
      getArtifactFile({ storageId: "abc", contentType: "application/pdf" })
    ).rejects.toThrow("Unable to find the node");
  });

  test("falls back to a generic message when the error carries none", async () => {
    mockResponse({ error: "Internal Server Error" });

    await expect(getArtifactFile({ storageId: "abc" })).rejects.toThrow(
      "Unable to load the artifact file"
    );
  });
});
