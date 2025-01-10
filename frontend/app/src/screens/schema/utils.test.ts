import { store } from "@/shared/stores";
import { schemaState } from "@/screens/schema/schema.atom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  generateGenericSchema,
  generateNodeSchema,
  generateProfileSchema,
} from "../../../tests/fake/schema";
import {
  getRootSchemaOfHierarchicalSchema,
  isGenericSchema,
  isHierarchicalSchema,
  isNodeSchema,
  isOfKind,
  isProfileSchema,
} from "./utils";

describe("Schema Utils", () => {
  describe("isOfKind", () => {
    it("should match when schema has the exact kind", () => {
      // GIVEN
      const schema = generateNodeSchema({ kind: "TestKind" });

      // WHEN
      const result = isOfKind("TestKind", schema);

      // THEN
      expect(result).toBe(true);
    });

    it("should match when schema inherits from the kind", () => {
      // GIVEN
      const schema = generateNodeSchema({
        kind: "Child",
        inherit_from: ["ParentKind"],
      });

      // WHEN
      const result = isOfKind("ParentKind", schema);

      // THEN
      expect(result).toBe(true);
    });

    it("should not match when schema has different kind and no inheritance", () => {
      // GIVEN
      const schema = generateNodeSchema({ kind: "Different" });

      // WHEN
      const result = isOfKind("TestKind", schema);

      // THEN
      expect(result).toBe(false);
    });

    it("should match all parent kinds when schema inherits from multiple", () => {
      // GIVEN
      const schema = generateNodeSchema({
        kind: "Child",
        inherit_from: ["Parent1", "Parent2"],
      });

      // WHEN
      const isParent1 = isOfKind("Parent1", schema);
      const isParent2 = isOfKind("Parent2", schema);

      // THEN
      expect(isParent1).toBe(true);
      expect(isParent2).toBe(true);
    });
  });

  describe("isGenericSchema", () => {
    it("should return true for a generic schema", () => {
      // GIVEN
      const schema = generateGenericSchema();

      // WHEN
      const result = isGenericSchema(schema);

      // THEN
      expect(result).toBe(true);
    });

    it("should return false for a non-generic schema", () => {
      // GIVEN
      const schema = generateNodeSchema();

      // WHEN
      const result = isGenericSchema(schema);

      // THEN
      expect(result).toBe(false);
    });
  });

  describe("isNodeSchema", () => {
    it("should return true for a node schema", () => {
      // GIVEN
      const schema = generateNodeSchema();

      // WHEN
      const result = isNodeSchema(schema);

      // THEN
      expect(result).toBe(true);
    });

    it("should return false for a non-node schema", () => {
      // GIVEN
      const schema = generateGenericSchema();

      // WHEN
      const result = isNodeSchema(schema);

      // THEN
      expect(result).toBe(false);
    });
  });

  describe("isProfileSchema", () => {
    it("should return true for a profile schema", () => {
      // GIVEN
      const schema = generateProfileSchema({ namespace: "Profile" });

      // WHEN
      const result = isProfileSchema(schema);

      // THEN
      expect(result).toBe(true);
    });

    it("should return false for a non-profile schema", () => {
      // GIVEN
      const schema = generateNodeSchema({ namespace: "Other" });

      // WHEN
      const result = isProfileSchema(schema);

      // THEN
      expect(result).toBe(false);
    });
  });

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
      expect(store.get).toHaveBeenCalledWith(schemaState);
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
      expect(store.get).toHaveBeenCalledWith(schemaState);
    });

    it("should return the original schema when no parent exists", () => {
      // GIVEN
      const schema = generateNodeSchema({ kind: "Orphan", parent: "NonExistent" });
      vi.spyOn(store, "get").mockReturnValue([schema]);

      // WHEN
      const result = getRootSchemaOfHierarchicalSchema(schema);

      // THEN
      expect(result).toBe(schema);
      expect(store.get).toHaveBeenCalledWith(schemaState);
    });

    it("should return the schema itself when it has no parent", () => {
      // GIVEN
      const schema = generateNodeSchema({ kind: "Root", parent: null });
      vi.spyOn(store, "get").mockReturnValue([schema]);

      // WHEN
      const result = getRootSchemaOfHierarchicalSchema(schema);

      // THEN
      expect(result).toBe(schema);
      expect(store.get).toHaveBeenCalledWith(schemaState);
    });
  });
});
