import { beforeEach, describe, expect, it, vi } from "vitest";

import { store } from "@/shared/stores";

import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import {
  getRootSchemaOfHierarchicalSchema,
  isHierarchicalSchema,
} from "@/entities/schema/utils/is-hierarchical-schema";

import { generateNodeSchema } from "../../../../tests/fake/schema";

describe("isHierarchicalSchema", () => {
  it("should return true when schema has a hierarchy", () => {
    // GIVEN
    const schema = generateNodeSchema({ hierarchy: "test-hierarchy" });

    // WHEN
    const result = isHierarchicalSchema(schema);

    // THEN
    expect(result).toBe(true);
  });

  it("should return false when schema has no hierarchy", () => {
    // GIVEN
    const schema = generateNodeSchema({ hierarchy: null });

    // WHEN
    const result = isHierarchicalSchema(schema);

    // THEN
    expect(result).toBe(false);
  });
});

describe("getRootSchemaOfHierarchicalSchema", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should return the root schema when found in direct parent hierarchy", () => {
    // GIVEN
    const rootSchema = generateNodeSchema({ kind: "Root" });
    const childSchema = generateNodeSchema({ kind: "Child", parent: "Root" });
    vi.spyOn(store, "get").mockReturnValue([rootSchema, childSchema]);

    // WHEN
    const result = getRootSchemaOfHierarchicalSchema(childSchema);

    // THEN
    expect(result).toBe(rootSchema);
    expect(store.get).toHaveBeenCalledWith(nodeSchemasAtom);
  });

  it("should return the root schema when found through multiple levels", () => {
    // GIVEN
    const rootSchema = generateNodeSchema({ kind: "Root" });
    const parentSchema = generateNodeSchema({ kind: "Parent", parent: "Root" });
    const childSchema = generateNodeSchema({ kind: "Child", parent: "Parent" });
    vi.spyOn(store, "get").mockReturnValue([rootSchema, parentSchema, childSchema]);

    // WHEN
    const result = getRootSchemaOfHierarchicalSchema(childSchema);

    // THEN
    expect(result).toBe(rootSchema);
    expect(store.get).toHaveBeenCalledWith(nodeSchemasAtom);
  });

  it("should return the original schema when no parent exists", () => {
    // GIVEN
    const schema = generateNodeSchema({ kind: "Orphan", parent: "NonExistent" });
    vi.spyOn(store, "get").mockReturnValue([schema]);

    // WHEN
    const result = getRootSchemaOfHierarchicalSchema(schema);

    // THEN
    expect(result).toBe(schema);
    expect(store.get).toHaveBeenCalledWith(nodeSchemasAtom);
  });

  it("should return the schema itself when it has no parent", () => {
    // GIVEN
    const schema = generateNodeSchema({ kind: "Root", parent: null });
    vi.spyOn(store, "get").mockReturnValue([schema]);

    // WHEN
    const result = getRootSchemaOfHierarchicalSchema(schema);

    // THEN
    expect(result).toBe(schema);
    expect(store.get).toHaveBeenCalledWith(nodeSchemasAtom);
  });
});
