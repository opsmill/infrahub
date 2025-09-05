import { beforeEach, describe, expect, it, vi } from "vitest";

import { removeRelationshipsFromApi } from "@/entities/nodes/relationships/api/remove-relationships-from-api";

import { removeRelationships } from "./remove-relationships";

vi.mock("@/entities/nodes/relationships/api/remove-relationships-from-api");

describe("removeRelationships", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should call removeRelationshipsFromApi with correctly transformed relationshipIds", async () => {
    // GIVEN
    const params = {
      branchName: "main",
      objectId: "object-1",
      relationshipName: "testRelationship",
      relationshipIds: ["rel-1", "rel-2"],
    };
    vi.mocked(removeRelationshipsFromApi).mockResolvedValueOnce(undefined!);

    // WHEN
    await removeRelationships(params);

    // THEN
    expect(removeRelationshipsFromApi).toHaveBeenCalledExactlyOnceWith({
      branchName: "main",
      objectId: "object-1",
      relationshipName: "testRelationship",
      relationshipIds: [{ id: "rel-1" }, { id: "rel-2" }],
    });
  });

  it("should handle an empty relationshipIds array", async () => {
    // GIVEN
    const params = {
      branchName: "main",
      objectId: "object-2",
      relationshipName: "emptyRelationship",
      relationshipIds: [],
    };
    vi.mocked(removeRelationshipsFromApi).mockResolvedValueOnce(undefined!);

    // WHEN
    await removeRelationships(params);

    // THEN
    expect(removeRelationshipsFromApi).toHaveBeenCalledExactlyOnceWith({
      branchName: "main",
      objectId: "object-2",
      relationshipName: "emptyRelationship",
      relationshipIds: [],
    });
  });

  it("should propagate errors thrown by removeRelationshipsFromApi", async () => {
    // GIVEN
    const params = {
      branchName: "main",
      objectId: "object-3",
      relationshipName: "errorRelationship",
      relationshipIds: ["rel-3"],
    };
    const error = new Error("API error");
    vi.mocked(removeRelationshipsFromApi).mockRejectedValueOnce(error);

    // WHEN/THEN
    await expect(removeRelationships(params)).rejects.toThrow("API error");

    expect(removeRelationshipsFromApi).toHaveBeenCalledExactlyOnceWith({
      branchName: "main",
      objectId: "object-3",
      relationshipName: "errorRelationship",
      relationshipIds: [{ id: "rel-3" }],
    });
  });
});
