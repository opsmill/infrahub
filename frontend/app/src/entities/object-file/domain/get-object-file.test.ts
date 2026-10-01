import { beforeEach, describe, expect, test, vi } from "vitest";

import { getObjectFile } from "@/entities/object-file/domain/get-object-file";

const getObjectFileFromApi = vi.hoisted(() => vi.fn());

vi.mock("@/entities/object-file/api/get-object-file-from-api", () => ({
  getObjectFileFromApi,
}));

describe("getObjectFile", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("rejects with the message the API returned", async () => {
    getObjectFileFromApi.mockResolvedValue({
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

    await expect(getObjectFile({ nodeId: "file-1", branchName: "main" })).rejects.toThrow(
      new Error("Unable to find the node abc / StorageObject in the database.")
    );
  });

  test("rejects with a generic message when the API returned none", async () => {
    getObjectFileFromApi.mockResolvedValue({ error: "Internal Server Error" });

    await expect(
      getObjectFile({ nodeId: "file-1", branchName: "main", contentType: "application/pdf" })
    ).rejects.toThrow(new Error("Unable to load the file"));
  });
});
