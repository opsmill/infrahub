import { describe, expect, test, vi } from "vitest";

import { ArtifactFileError } from "@/entities/artifacts/domain/model/artifact-file-error";
import { getArtifactFile } from "@/entities/artifacts/domain/use-cases/get-artifact-file";

const getArtifactFileFromApi = vi.hoisted(() => vi.fn());

vi.mock("@/entities/artifacts/api/get-artifact-file-from-api", () => ({ getArtifactFileFromApi }));

describe("getArtifactFile", () => {
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
      response: { status: 404 },
    });

    await expect(getArtifactFile({ storageId: "abc" })).rejects.toMatchObject({
      message: "Unable to find the node abc / StorageObject in the database.",
    });
  });

  test("rejects with a generic message when the API returned none", async () => {
    getArtifactFileFromApi.mockResolvedValue({
      error: "Internal Server Error",
      response: { status: 500 },
    });

    await expect(
      getArtifactFile({ storageId: "abc", contentType: "application/pdf" })
    ).rejects.toMatchObject({ message: "Unable to load the artifact file" });
  });

  test("rejects with the HTTP status of the response", async () => {
    getArtifactFileFromApi.mockResolvedValue({
      error: {
        data: null,
        errors: [
          {
            message: "The stored content abc failed its integrity check and was not served.",
            extensions: { code: 409 },
          },
        ],
      },
      response: { status: 409 },
    });

    await expect(getArtifactFile({ storageId: "abc" })).rejects.toMatchObject(
      new ArtifactFileError(
        "The stored content abc failed its integrity check and was not served.",
        409
      )
    );
    await expect(getArtifactFile({ storageId: "abc" })).rejects.toBeInstanceOf(ArtifactFileError);
  });

  test("rejects with the HTTP status of the response for a binary file", async () => {
    getArtifactFileFromApi.mockResolvedValue({
      error: { data: null, errors: [{ message: "Refused", extensions: { code: 409 } }] },
      response: { status: 409 },
    });

    await expect(
      getArtifactFile({ storageId: "abc", contentType: "application/pdf" })
    ).rejects.toMatchObject({ message: "Refused", status: 409 });
  });
});
