import { beforeEach, describe, expect, test, vi } from "vitest";

import { getArtifactFile } from "@/entities/artifacts/domain/get-artifact-file";

const getArtifactFileFromApi = vi.hoisted(() => vi.fn());

vi.mock("@/entities/artifacts/api/get-artifact-file-from-api", () => ({ getArtifactFileFromApi }));

describe("getArtifactFile", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("rejects with the message the API returned", async () => {
    getArtifactFileFromApi.mockResolvedValue({
      error: {
        data: null,
        errors: [
          {
            message: "Unable to find the node abc / StorageObject in the database.",
            extensions: { code: 404 },
          },
        ],
      },
    });

    await expect(getArtifactFile({ storageId: "abc" })).rejects.toThrow(
      new Error("Unable to find the node abc / StorageObject in the database.")
    );
  });

  test("rejects with a generic message when the API returned none", async () => {
    getArtifactFileFromApi.mockResolvedValue({ error: "Internal Server Error" });

    await expect(
      getArtifactFile({ storageId: "abc", contentType: "application/pdf" })
    ).rejects.toThrow(new Error("Unable to load the artifact file"));
  });
});
