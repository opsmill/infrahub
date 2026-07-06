import { beforeEach, describe, expect, it, vi } from "vitest";

import { addRelationshipsToApi } from "@/entities/nodes/relationships/api/add-relationships-from-api";

import { addRelationships } from "./add-relationships";

vi.mock("@/entities/nodes/relationships/api/add-relationships-from-api");

describe("addRelationships", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should call addRelationshipsToApi with correctly transformed relationshipIds", async () => {
    // GIVEN
    const params = {
      branchName: "main",
      objectId: "object-1",
      relationshipName: "testRelationship",
      relationshipIds: ["rel-1", "rel-2", "rel-3"],
    };
    vi.mocked(addRelationshipsToApi).mockResolvedValueOnce(undefined!);

    // WHEN
    await addRelationships(params);

    // THEN
    expect(addRelationshipsToApi).toHaveBeenCalledExactlyOnceWith({
      branchName: "main",
      objectId: "object-1",
      relationshipName: "testRelationship",
      relationshipIds: [{ id: "rel-1" }, { id: "rel-2" }, { id: "rel-3" }],
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
    vi.mocked(addRelationshipsToApi).mockResolvedValueOnce(undefined!);

    // WHEN
    await addRelationships(params);

    // THEN
    expect(addRelationshipsToApi).toHaveBeenCalledExactlyOnceWith({
      branchName: "main",
      objectId: "object-2",
      relationshipName: "emptyRelationship",
      relationshipIds: [],
    });
  });

  it("should propagate errors thrown by addRelationshipsToApi", async () => {
    // GIVEN
    const params = {
      branchName: "main",
      objectId: "object-3",
      relationshipName: "errorRelationship",
      relationshipIds: ["rel-3"],
    };
    const error = new Error("API error");
    vi.mocked(addRelationshipsToApi).mockRejectedValueOnce(error);

    // WHEN/THEN
    await expect(addRelationships(params)).rejects.toThrow("API error");

    expect(addRelationshipsToApi).toHaveBeenCalledExactlyOnceWith({
      branchName: "main",
      objectId: "object-3",
      relationshipName: "errorRelationship",
      relationshipIds: [{ id: "rel-3" }],
    });
  });

  it("should handle a single relationship ID", async () => {
    // GIVEN
    const params = {
      branchName: "main",
      objectId: "object-4",
      relationshipName: "singleRelationship",
      relationshipIds: ["single-id"],
    };
    vi.mocked(addRelationshipsToApi).mockResolvedValueOnce(undefined!);

    // WHEN
    await addRelationships(params);

    // THEN
    expect(addRelationshipsToApi).toHaveBeenCalledExactlyOnceWith({
      branchName: "main",
      objectId: "object-4",
      relationshipName: "singleRelationship",
      relationshipIds: [{ id: "single-id" }],
    });
  });
});
