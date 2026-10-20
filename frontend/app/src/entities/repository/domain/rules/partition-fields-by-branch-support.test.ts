import { describe, expect, it } from "vitest";

import { partitionFieldsByBranchSupport } from "@/entities/repository/domain/rules/partition-fields-by-branch-support";

import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../tests/fake/schema";

describe("partitionFieldsByBranchSupport", () => {
  it("should put an aware attribute in the branch-scoped set", () => {
    // GIVEN
    const schema = generateNodeSchema({
      branch: "agnostic",
      attributes: [generateAttributeSchema({ name: "ref", branch: "aware" })],
      relationships: [],
    });

    // WHEN
    const { branchScoped, repositoryWide } = partitionFieldsByBranchSupport(schema);

    // THEN
    expect(branchScoped.attributes.map((attribute) => attribute.name)).toEqual(["ref"]);
    expect(repositoryWide.attributes).toEqual([]);
  });

  it("should put a local attribute in the branch-scoped set", () => {
    // GIVEN
    const schema = generateNodeSchema({
      branch: "agnostic",
      attributes: [generateAttributeSchema({ name: "commit", branch: "local" })],
      relationships: [],
    });

    // WHEN
    const { branchScoped, repositoryWide } = partitionFieldsByBranchSupport(schema);

    // THEN
    expect(branchScoped.attributes.map((attribute) => attribute.name)).toEqual(["commit"]);
    expect(repositoryWide.attributes).toEqual([]);
  });

  it("should put an agnostic attribute in the repository-wide set", () => {
    // GIVEN
    const schema = generateNodeSchema({
      branch: "aware",
      attributes: [generateAttributeSchema({ name: "name", branch: "agnostic" })],
      relationships: [],
    });

    // WHEN
    const { branchScoped, repositoryWide } = partitionFieldsByBranchSupport(schema);

    // THEN
    expect(repositoryWide.attributes.map((attribute) => attribute.name)).toEqual(["name"]);
    expect(branchScoped.attributes).toEqual([]);
  });

  it("should fall back to the node declaration for a field that declares no branch support", () => {
    // GIVEN
    const agnosticNode = generateNodeSchema({
      branch: "agnostic",
      attributes: [generateAttributeSchema({ name: "name", branch: undefined })],
      relationships: [generateRelationshipSchema({ name: "tags", branch: undefined })],
    });
    const localNode = generateNodeSchema({
      branch: "local",
      attributes: [generateAttributeSchema({ name: "commit", branch: null })],
      relationships: [generateRelationshipSchema({ name: "checks", branch: null })],
    });

    // WHEN
    const agnosticResult = partitionFieldsByBranchSupport(agnosticNode);
    const localResult = partitionFieldsByBranchSupport(localNode);

    // THEN
    expect(agnosticResult.repositoryWide.attributes.map((attribute) => attribute.name)).toEqual([
      "name",
    ]);
    expect(
      agnosticResult.repositoryWide.relationships.map((relationship) => relationship.name)
    ).toEqual(["tags"]);
    expect(agnosticResult.branchScoped.attributes).toEqual([]);
    expect(agnosticResult.branchScoped.relationships).toEqual([]);

    expect(localResult.branchScoped.attributes.map((attribute) => attribute.name)).toEqual([
      "commit",
    ]);
    expect(localResult.branchScoped.relationships.map((relationship) => relationship.name)).toEqual(
      ["checks"]
    );
    expect(localResult.repositoryWide.attributes).toEqual([]);
    expect(localResult.repositoryWide.relationships).toEqual([]);
  });

  it("should partition relationships by the same rule as attributes", () => {
    // GIVEN
    const schema = generateNodeSchema({
      branch: "agnostic",
      attributes: [],
      relationships: [
        generateRelationshipSchema({ name: "credential", branch: "agnostic" }),
        generateRelationshipSchema({ name: "tags", branch: "aware" }),
        generateRelationshipSchema({ name: "checks", branch: "local" }),
      ],
    });

    // WHEN
    const { branchScoped, repositoryWide } = partitionFieldsByBranchSupport(schema);

    // THEN
    expect(repositoryWide.relationships.map((relationship) => relationship.name)).toEqual([
      "credential",
    ]);
    expect(branchScoped.relationships.map((relationship) => relationship.name)).toEqual([
      "tags",
      "checks",
    ]);
  });

  it("should place every field in exactly one of the two sets", () => {
    // GIVEN
    const schema = generateNodeSchema({
      branch: "agnostic",
      attributes: [
        generateAttributeSchema({ name: "name", branch: "agnostic" }),
        generateAttributeSchema({ name: "commit", branch: "local" }),
        generateAttributeSchema({ name: "ref", branch: "aware" }),
      ],
      relationships: [
        generateRelationshipSchema({ name: "credential", branch: "agnostic" }),
        generateRelationshipSchema({ name: "transformations", branch: undefined }),
      ],
    });

    // WHEN
    const { branchScoped, repositoryWide } = partitionFieldsByBranchSupport(schema);

    // THEN
    const allNames = [
      ...repositoryWide.attributes,
      ...repositoryWide.relationships,
      ...branchScoped.attributes,
      ...branchScoped.relationships,
    ].map((field) => field.name);
    expect([...allNames].sort()).toEqual([
      "commit",
      "credential",
      "name",
      "ref",
      "transformations",
    ]);
  });

  it("should return empty sets for a schema with no attributes and no relationships", () => {
    // GIVEN
    const schema = generateNodeSchema({ branch: "agnostic", attributes: [], relationships: [] });

    // WHEN
    const { branchScoped, repositoryWide } = partitionFieldsByBranchSupport(schema);

    // THEN
    expect(repositoryWide).toEqual({ attributes: [], relationships: [] });
    expect(branchScoped).toEqual({ attributes: [], relationships: [] });
  });
});
